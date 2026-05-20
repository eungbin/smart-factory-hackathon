from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas import WorkOrderCreate
from app.work_orders import generate_work_order


class WorkOrderTests(unittest.TestCase):
    def test_generated_work_order_has_required_rag_fields(self) -> None:
        order = generate_work_order(WorkOrderCreate(asset_id="INJ-03"))
        self.assertGreaterEqual(len(order.inspection_points), 3)
        self.assertGreaterEqual(len(order.tools), 3)
        self.assertGreaterEqual(len(order.consumables), 1)
        self.assertGreaterEqual(len(order.safety_rules), 2)
        self.assertGreaterEqual(len(order.checklist), 3)
        self.assertGreaterEqual(len(order.manual_sources), 1)
        self.assertIn("RUL", order.dispatch_message)


if __name__ == "__main__":
    unittest.main()
