import unittest

from sdv_console.core.event_bus import EventBus
from sdv_console.core.vehicle_state import VehicleState
from sdv_console.services.history import HistoryService
from sdv_console.services.ota import OTAService


class TestOTASecurityAndRollback(unittest.TestCase):
    def setUp(self):
        self.events = EventBus()
        self.state = VehicleState(self.events)
        self.history = HistoryService(self.events)
        self.ota = OTAService(self.state, self.events, self.history)
        self.state.set_firmware("v1.1.0")
        self.state.update_ecu("battery", firmware="v1.1.0", status="HEALTHY", health=100)

    def test_delta_package_validation_and_rollback(self):
        package = self.ota._plan_package("v1.1.0", "v1.2.0")
        self.assertEqual(package["package_type"], "delta")
        self.assertEqual(package["base_version"], "v1.1.0")
        self.assertTrue(self.ota.verify_integrity(package))
        self.assertTrue(self.ota.verify_authenticity(package))

        result = self.ota.start("Battery ECU", "v1.2.0", requested_by="eng-user", role="engineering", pin="4321")
        self.assertTrue(result["ok"], result)

        self.ota.tick(10.0)
        self.assertEqual(self.state.snapshot()["firmware"], "v1.2.0")

        rollback = self.ota.rollback(requested_by="eng-user", role="engineering", pin="4321")
        self.assertTrue(rollback["ok"], rollback)
        self.assertEqual(self.state.snapshot()["firmware"], "v1.1.0")

    def test_pin_required_and_failed_auth_blocks_ota(self):
        self.assertFalse(self.ota.authorize_request(requested_by="eng-user", role="engineering", pin=None))

        bad = self.ota.start("Battery ECU", "v1.2.0", requested_by="eng-user", role="engineering", pin="0000")
        self.assertFalse(bad["ok"], bad)
        self.assertEqual(bad["error"], "UNAUTHORIZED_OTA_REQUEST")

        ok = self.ota.authenticate_pin("4321")
        self.assertTrue(ok["ok"], ok)


if __name__ == "__main__":
    unittest.main()
