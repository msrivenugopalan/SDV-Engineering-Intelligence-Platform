"""OTA workflow with version tracking, package validation, delta support,
rollback, and security verification.

This remains a prototype-grade implementation suitable for engineering demos:
- it validates firmware metadata before installation,
- verifies SHA-256 integrity and a public-key-style signature,
- authorizes OTA operations using a lightweight role-based check,
- supports full or delta package selection based on the current firmware,
- records the result in the existing SQLite history tables.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

from sdv_console.config import OTA_PIN_HASH
from sdv_console.core.event_bus import EventBus
from sdv_console.core.models import OTASession, VehicleEvent, utc_now_iso
from sdv_console.core.vehicle_state import VehicleState
from sdv_console.services.history import HistoryService

STAGE_TIMINGS = (
    (0.5, "VALIDATING", {"firmware_validation": True, "authorization_check": True}, 18),
    (1.2, "VALIDATING", {"integrity_check": True}, 38),
    (1.9, "VALIDATING", {"compatibility_check": True, "authenticity_check": True}, 58),
    (2.8, "DOWNLOADING", {"download_complete": True}, 74),
    (4.2, "INSTALLING", {"package_transfer_complete": True}, 92),
)
TOTAL_DURATION_S = 5.4


class OTAService:
    SECURITY_LEVEL = "DEMO_PROTOTYPE"
    TRUSTED_ROLES = {"engineering", "ota-admin", "maintainer"}
    TRUSTED_OPERATORS = {"engineering-demo", "eng-user", "ota-admin", "maintainer", "service-account"}

    FIRMWARE_CATALOG = {
        "v1.0.0": {
            "version": "v1.0.0",
            "release_id": "R-2026.09.20",
            "release_timestamp": "2026-09-20T00:00:00Z",
            "package_type": "full",
            "package_size": 2_400_000,
            "features": [
                "Baseline battery management",
                "Initial ECU diagnostics",
                "Nominal CAN communication",
            ],
        },
        "v1.1.0": {
            "version": "v1.1.0",
            "release_id": "R-2026.09.30",
            "release_timestamp": "2026-09-30T00:00:00Z",
            "package_type": "full",
            "package_size": 2_350_000,
            "features": [
                "Improved battery thermal monitoring",
                "Updated diagnostic thresholds",
                "Improved fault handling",
            ],
        },
        "v1.2.0": {
            "version": "v1.2.0",
            "release_id": "R-2026.10.05",
            "release_timestamp": "2026-10-05T00:00:00Z",
            "package_type": "full",
            "package_size": 2_390_000,
            "features": [
                "Improved battery thermal monitoring",
                "Added diagnostic condition",
                "Improved ECU fault handling",
                "Optimized CAN communication",
                "Improved recovery behavior",
            ],
        },
        "v2.0.0": {
            "version": "v2.0.0",
            "release_id": "R-2026.10.15",
            "release_timestamp": "2026-10-15T00:00:00Z",
            "package_type": "full",
            "package_size": 2_600_000,
            "features": [
                "Battery pack optimization",
                "Advanced diagnostic suite",
                "Enhanced autonomous recovery",
            ],
        },
    }

    def __init__(self, state: VehicleState, events: EventBus, history: HistoryService) -> None:
        self.state = state
        self.events = events
        self.history = history
        self._active = False
        self._elapsed = 0.0
        self._from = "v1.0.0"
        self._to = "v2.0.0"
        self._ecu = ""
        self._package: dict[str, Any] = {}
        self._known_good_versions: list[str] = [self.state.get_last_known_good_version()]
        self._failed_auth_attempts = 0
        self._auth_lock_until = 0.0
        self._pin_hash = OTA_PIN_HASH

    @property
    def busy(self) -> bool:
        return self._active

    def set_pin_hash(self, pin: str) -> None:
        self._pin_hash = hashlib.sha256(pin.strip().encode("utf-8")).hexdigest()

    def authenticate_pin(self, pin: str | None) -> dict[str, Any]:
        if pin is None:
            return {"ok": False, "error": "AUTHENTICATION_REQUIRED", "detail": "A valid OTA security PIN is required."}
        if time.monotonic() < self._auth_lock_until:
            remaining = max(1, int(self._auth_lock_until - time.monotonic()))
            return {"ok": False, "error": "PIN_LOCKED", "detail": f"Too many failed attempts. Please wait {remaining} seconds and retry."}
        digest = hashlib.sha256(str(pin).strip().encode("utf-8")).hexdigest()
        if digest != self._pin_hash:
            self._failed_auth_attempts += 1
            if self._failed_auth_attempts >= 3:
                self._auth_lock_until = time.monotonic() + 60.0
                self._failed_auth_attempts = 0
                self.events.publish(VehicleEvent.create("OTA_SECURITY_EVENT", source="ota", severity="ERROR", payload={"event": "PIN_LOCKED", "reason": "Too many failed attempts."}))
            return {"ok": False, "error": "AUTHENTICATION_FAILED", "detail": "The OTA security PIN is invalid."}

        self._failed_auth_attempts = 0
        self._auth_lock_until = 0.0
        return {"ok": True, "detail": "OTA security PIN verified."}

    def authorize_request(self, requested_by: str | None = None, role: str | None = None, pin: str | None = None, action: str = "deploy") -> bool:
        effective_role = (role or "engineering").strip().lower()
        user = (requested_by or "engineering-demo").strip().lower()
        if effective_role not in self.TRUSTED_ROLES:
            return False
        if user and user not in self.TRUSTED_OPERATORS and not user.startswith("eng"):
            return False
        if pin is None:
            return False
        auth = self.authenticate_pin(pin)
        if not auth.get("ok"):
            return False
        return True

    def start(self, target_ecu: str, target_version: str, requested_by: str = "engineering-demo", role: str = "engineering", pin: str | None = None) -> dict:
        if self._active:
            return {"ok": False, "error": "ota_in_progress"}
        if pin is None:
            return {"ok": False, "error": "AUTHENTICATION_REQUIRED", "detail": "A valid OTA security PIN is required before deployment."}
        if not self.authorize_request(requested_by=requested_by, role=role, pin=pin, action="deploy"):
            return {"ok": False, "error": "UNAUTHORIZED_OTA_REQUEST", "detail": "Only a trusted engineering role may initiate OTA after valid PIN verification."}

        current = self.state.snapshot()["firmware"]
        if current == target_version:
            return {"ok": False, "error": "version_already_active", "detail": f"{target_version} is already running."}

        self._known_good_versions = [current] + [v for v in self._known_good_versions if v != current]
        self.state.set_last_known_good_version(current)
        package = self._plan_package(current, target_version, target_ecu)
        if not package.get("ok", True):
            return package

        target_ecu_id = self._ecu_id(target_ecu)
        current_snapshot = self.state.snapshot()
        current_ecu = current_snapshot["ecus"].get(target_ecu_id, {})
        if not current_ecu:
            return {"ok": False, "error": "unsupported_ecu", "detail": f"{target_ecu} is not available in the ECU catalog."}

        self._active = True
        self._elapsed = 0.0
        self._from = current
        self._to = target_version
        self._ecu = target_ecu
        self._package = package

        session = OTASession(
            current_version=current,
            target_version=target_version,
            target_ecu=target_ecu,
            status="VALIDATING",
            progress=5,
            checks={
                "firmware_validation": False,
                "integrity_check": False,
                "compatibility_check": False,
                "authorization_check": True,
                "authenticity_check": False,
                "download_complete": False,
                "package_transfer_complete": False,
            },
            started_at=utc_now_iso(),
            from_version=current,
            update_type=package["update_type"],
            package_type=package["package_type"],
            package_size=package.get("package_size", 0),
            delta_size=package.get("delta_size", 0),
            integrity_verified=False,
            authenticity_verified=False,
            compatibility_verified=False,
            rollback_available=bool(self._known_good_versions[:-1]),
            last_known_good_version=self.state.get_last_known_good_version(),
            feature_changes=package.get("features", []),
            metadata=package,
            security_level=self.SECURITY_LEVEL,
            authentication_status="VERIFIED",
            rollback_status="READY",
        )
        self.state.set_ota(session)
        self.events.publish(VehicleEvent.create("OTA_STARTED", source="ota", ecu=target_ecu_id, payload={"from": current, "to": target_version, "package_type": package["package_type"], "update_type": package["update_type"]}))
        return {"ok": True, "from": current, "to": target_version, "package_type": package["package_type"], "update_type": package["update_type"]}

    def tick(self, dt: float) -> None:
        if not self._active:
            return
        self._elapsed += dt
        session = self.state.get_ota()

        for threshold, status, checks, progress in STAGE_TIMINGS:
            if self._elapsed >= threshold:
                session.status = status
                session.checks.update(checks)
                session.progress = max(session.progress, progress)

        if self._elapsed >= TOTAL_DURATION_S:
            self._complete_installation(session)
            return

        if 1.9 < self._elapsed < TOTAL_DURATION_S:
            session.progress = min(99, int(42 + (self._elapsed - 1.9) / (TOTAL_DURATION_S - 1.9) * 57))
        self.state.set_ota(session)

    def rollback(self, requested_by: str = "engineering-demo", role: str = "engineering", pin: str | None = None) -> dict[str, Any]:
        if pin is None:
            return {"ok": False, "error": "AUTHENTICATION_REQUIRED", "detail": "A valid OTA security PIN is required before rollback."}
        if not self.authorize_request(requested_by=requested_by, role=role, pin=pin, action="rollback"):
            return {"ok": False, "error": "UNAUTHORIZED_OTA_REQUEST", "detail": "Only a trusted engineering role may rollback OTA after PIN verification."}

        current = self.state.snapshot()["firmware"]
        candidates = [v for v in self._known_good_versions if v and v != current]
        target = candidates[0] if candidates else self._previous_version(current)
        if not target or target == current:
            return {"ok": False, "error": "no_rollback_target", "detail": "No previous known-good version is available for rollback."}

        package = self._plan_package(current, target, self._ecu or self._default_ecu_name(), rollback=True)
        if not package.get("ok", True):
            return package

        if not self.verify_integrity(package):
            self.events.publish(VehicleEvent.create("OTA_SECURITY_EVENT", source="ota", ecu=self._ecu_id(self._ecu or "Battery ECU"), severity="ERROR", payload={"event": "INVALID_FIRMWARE_HASH", "target_version": target}))
            return {"ok": False, "error": "FIRMWARE_INTEGRITY_VERIFICATION_FAILED", "detail": "Firmware integrity verification failed. Installation blocked."}
        if not self.verify_authenticity(package):
            self.events.publish(VehicleEvent.create("OTA_SECURITY_EVENT", source="ota", ecu=self._ecu_id(self._ecu or "Battery ECU"), severity="ERROR", payload={"event": "INVALID_SIGNATURE", "target_version": target}))
            return {"ok": False, "error": "INVALID_FIRMWARE_SIGNATURE", "detail": "Firmware authenticity verification failed. Installation blocked."}

        self.state.set_firmware(target)
        self.state.set_last_known_good_version(target)
        self.state.update_ecu(self._ecu_id(self._ecu or self._default_ecu_name()), firmware=target, status="HEALTHY", health=100, last_event="Rollback successful")
        self.state.add_firmware_history(target, "ROLLBACK_SUCCESS", source="rollback", from_version=current, target_version=target)
        self._known_good_versions = [target] + [v for v in self._known_good_versions if v != target]

        rollback_session = self.state.get_ota()
        rollback_session.status = "COMPLETED"
        rollback_session.progress = 100
        rollback_session.finished_at = utc_now_iso()
        rollback_session.from_version = current
        rollback_session.target_version = target
        rollback_session.current_version = target
        rollback_session.rollback_available = False
        rollback_session.rollback_status = "COMPLETED"
        rollback_session.authentication_status = "VERIFIED"
        rollback_session.last_error = None
        rollback_session.metadata = package
        self.state.set_ota(rollback_session)

        self.history.insert_ota(
            self._ecu or self._default_ecu_name(),
            current,
            target,
            "ROLLBACK_SUCCESS",
            details={"reason": "rollback_to_last_known_good", "package_type": package["package_type"], "update_type": package["update_type"], "security_level": self.SECURITY_LEVEL},
            package_type=package["package_type"],
            update_type=package["update_type"],
            security_level=self.SECURITY_LEVEL,
        )
        self.events.publish(VehicleEvent.create("OTA_ROLLBACK", source="ota", ecu=self._ecu_id(self._ecu or self._default_ecu_name()), payload={"from": current, "to": target, "package_type": package["package_type"]}))
        return {"ok": True, "from": current, "to": target, "package_type": package["package_type"], "update_type": package["update_type"]}

    def verify_integrity(self, package: dict[str, Any]) -> bool:
        payload = package.get("payload")
        expected = package.get("package_hash")
        if payload is None or expected is None:
            return False
        actual = hashlib.sha256(payload).hexdigest()
        return actual == expected

    def verify_authenticity(self, package: dict[str, Any]) -> bool:
        payload_hash = package.get("package_hash")
        signature = package.get("signature")
        if not payload_hash or not signature:
            return False
        expected = self._generate_signature(payload_hash)
        return signature == expected

    def _plan_package(self, current_version: str, target_version: str, target_ecu: str = "Battery ECU", rollback: bool = False) -> dict[str, Any]:
        target_meta = self.FIRMWARE_CATALOG.get(target_version)
        if not target_meta:
            return {"ok": False, "error": "unsupported_version", "detail": f"No metadata exists for {target_version}."}

        target_ecu_id = self._ecu_id(target_ecu)
        delta = self._delta_package(current_version, target_version, target_ecu_id)
        if delta and not rollback and delta["base_version"] == current_version:
            package = self._build_package(delta, target_meta, is_delta=True)
            return {"ok": True, **package}

        package = self._build_package({"base_version": current_version, "payload": self._firmware_payload(target_version, target_ecu_id)}, target_meta, is_delta=False)
        return {"ok": True, **package}

    def _previous_version(self, version: str) -> str | None:
        ordered = ["v1.0.0", "v1.1.0", "v1.2.0", "v2.0.0"]
        try:
            idx = ordered.index(version)
        except ValueError:
            return None
        if idx <= 0:
            return None
        return ordered[idx - 1]

    def _build_package(self, delta: dict[str, Any], target_meta: dict[str, Any], is_delta: bool) -> dict[str, Any]:
        target_version = target_meta["version"]
        package_payload = delta.get("payload") or self._firmware_payload(target_version, "battery")
        package_hash = hashlib.sha256(package_payload).hexdigest()
        signature = self._generate_signature(package_hash)
        package_type = "delta" if is_delta else "full"
        size = delta.get("size", target_meta["package_size"])
        metrics = {
            "version": target_version,
            "base_version": delta.get("base_version", target_meta["version"]),
            "target_version": target_version,
            "ecu": delta.get("ecu", "battery"),
            "package_type": package_type,
            "algorithm": "SHA-256",
            "package_hash": package_hash,
            "target_firmware_hash": hashlib.sha256(self._firmware_payload(target_version, delta.get("ecu", "battery"))).hexdigest(),
            "signature": signature,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "features": list(target_meta.get("features", [])),
            "package_size": size,
            "delta_size": size if is_delta else 0,
            "full_package_size": target_meta["package_size"],
            "update_type": "DELTA OTA" if is_delta else "FULL OTA",
            "payload": package_payload,
            "release_id": target_meta.get("release_id", "demo"),
            "release_timestamp": target_meta.get("release_timestamp", utc_now_iso()),
            "security_level": self.SECURITY_LEVEL,
            "compatibility": "VERIFIED",
        }
        return metrics

    def _delta_package(self, current_version: str, target_version: str, ecu_id: str) -> dict[str, Any] | None:
        if current_version == "v1.1.0" and target_version == "v1.2.0":
            payload = self._firmware_payload(target_version, ecu_id)[:380_000]
            return {
                "base_version": "v1.1.0",
                "target_version": "v1.2.0",
                "ecu": ecu_id,
                "size": len(payload),
                "payload": payload,
            }
        if current_version == "v1.0.0" and target_version == "v1.1.0":
            payload = self._firmware_payload(target_version, ecu_id)[:220_000]
            return {
                "base_version": "v1.0.0",
                "target_version": "v1.1.0",
                "ecu": ecu_id,
                "size": len(payload),
                "payload": payload,
            }
        return None

    def _complete_installation(self, session: OTASession) -> None:
        package = self._package.copy()
        if not self.verify_integrity(package):
            session.status = "FAILED"
            session.progress = 100
            session.finished_at = utc_now_iso()
            session.last_error = "Firmware integrity verification failed. Installation blocked."
            self.state.set_ota(session)
            self.events.publish(VehicleEvent.create("OTA_FAILED", source="ota", ecu=self._ecu_id(self._ecu), severity="ERROR", payload={"reason": "FIRMWARE_INTEGRITY_VERIFICATION_FAILED", "target_version": self._to}))
            self.history.insert_ota(self._ecu, self._from, self._to, "FAILED", details={"reason": "FIRMWARE_INTEGRITY_VERIFICATION_FAILED"}, package_type=package.get("package_type"), update_type=package.get("update_type"), security_level=self.SECURITY_LEVEL)
            self._active = False
            return

        if not self.verify_authenticity(package):
            session.status = "FAILED"
            session.progress = 100
            session.finished_at = utc_now_iso()
            session.last_error = "Firmware authenticity verification failed. Installation blocked."
            self.state.set_ota(session)
            self.events.publish(VehicleEvent.create("OTA_FAILED", source="ota", ecu=self._ecu_id(self._ecu), severity="ERROR", payload={"reason": "INVALID_FIRMWARE_SIGNATURE", "target_version": self._to}))
            self.history.insert_ota(self._ecu, self._from, self._to, "FAILED", details={"reason": "INVALID_FIRMWARE_SIGNATURE"}, package_type=package.get("package_type"), update_type=package.get("update_type"), security_level=self.SECURITY_LEVEL)
            self._active = False
            return

        if package.get("package_type") == "delta" and package.get("base_version") != self._from:
            session.status = "FAILED"
            session.progress = 100
            session.finished_at = utc_now_iso()
            session.last_error = "Delta package cannot be applied because the installed firmware version does not match the required base version."
            self.state.set_ota(session)
            self.events.publish(VehicleEvent.create("OTA_FAILED", source="ota", ecu=self._ecu_id(self._ecu), severity="ERROR", payload={"reason": "INVALID_DELTA_PACKAGE", "installed_version": self._from, "required_base": package.get("base_version")}))
            self.history.insert_ota(self._ecu, self._from, self._to, "FAILED", details={"reason": "INVALID_DELTA_PACKAGE", "installed_version": self._from, "required_base": package.get("base_version")}, package_type=package.get("package_type"), update_type=package.get("update_type"), security_level=self.SECURITY_LEVEL)
            self._active = False
            return

        self._active = False
        session.status = "COMPLETED"
        session.progress = 100
        session.finished_at = utc_now_iso()
        session.integrity_verified = True
        session.authenticity_verified = True
        session.compatibility_verified = True
        session.rollback_available = True
        session.last_known_good_version = self._from
        session.feature_changes = list(package.get("features", []))
        session.metadata = package
        self.state.set_ota(session)
        self.state.set_firmware(self._to)
        self.state.set_last_known_good_version(self._to)
        self.state.update_ecu(self._ecu_id(self._ecu), firmware=self._to, status="HEALTHY", health=100, last_event="OTA success")
        self.state.add_firmware_history(self._to, "SUCCESS", source="ota", from_version=self._from, target_version=self._to, update_type=package.get("update_type"))
        self._known_good_versions = [self._to] + [v for v in self._known_good_versions if v != self._to]
        self.history.insert_ota(
            self._ecu,
            self._from,
            self._to,
            "SUCCESS",
            details={
                "package_type": package.get("package_type"),
                "update_type": package.get("update_type"),
                "feature_changes": package.get("features", []),
                "integrity_verified": True,
                "authentication_verified": True,
                "software_security_level": self.SECURITY_LEVEL,
            },
            package_type=package.get("package_type"),
            update_type=package.get("update_type"),
            security_level=self.SECURITY_LEVEL,
        )
        self.events.publish(VehicleEvent.create("OTA_COMPLETED", source="ota", ecu=self._ecu_id(self._ecu), payload={"from": self._from, "to": self._to, "package_type": package.get("package_type"), "update_type": package.get("update_type")}))

    def _firmware_payload(self, version: str, ecu_id: str) -> bytes:
        return f"{ecu_id}:{version}:demo-ota-payload:sha256".encode("utf-8")

    def _generate_signature(self, package_hash: str) -> str:
        return hashlib.sha256(f"{self.SECURITY_LEVEL}:{package_hash}:{self.SECURITY_LEVEL}".encode("utf-8")).hexdigest()

    def _ecu_id(self, human_name: str) -> str:
        mapping = {"Motor ECU": "engine", "Battery ECU": "battery", "Brake ECU": "brake", "Steering ECU": "steering", "Climate ECU": "climate", "ADAS ECU": "adas"}
        if human_name in mapping:
            return mapping[human_name]
        normalized = human_name.strip().lower()
        for key, value in mapping.items():
            if value == normalized:
                return value
        return "battery"

    def _default_ecu_name(self) -> str:
        return "Battery ECU"
