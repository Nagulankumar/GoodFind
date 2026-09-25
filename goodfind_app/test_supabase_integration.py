"""
Comprehensive tests for GoodFind Supabase database & storage integration.
Tests password hashing, image template filters, data adapter operations,
and fallback functionality.
"""
import unittest
import os
import io
from PIL import Image

import mock_data as db
import supabase_client
from app import app, img_src_filter, _validate_item_form


class TestSupabaseIntegration(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.req_context = app.test_request_context("/")
        self.req_context.push()

    def tearDown(self):
        self.req_context.pop()

    def test_image_src_filter(self):
        """Test that img_src filter correctly preserves full URLs and resolves local paths."""
        remote_url = "https://xyz.supabase.co/storage/v1/object/public/item-photos/sample.jpg"
        self.assertEqual(img_src_filter(remote_url), remote_url)

        local_path = "uploads/seed/phone_owner.png"
        resolved = img_src_filter(local_path)
        self.assertTrue(resolved.endswith("uploads/seed/phone_owner.png"))
        self.assertTrue(resolved.startswith("/static/"))

        self.assertEqual(img_src_filter(""), "")

    def test_password_hashing(self):
        """Test user creation with secure password hashing."""
        user = db.create_user("Test User", "testuser@vsbec.ac.in", "secret123", "org-001", role="member")
        self.assertIn("password_hash", user)
        self.assertTrue(db.verify_user_password(user, "secret123"))
        self.assertFalse(db.verify_user_password(user, "wrongpassword"))

    def test_item_form_validation(self):
        """Test form validation rules."""
        # Missing fields
        errors = _validate_item_form({})
        self.assertIn("name", errors)
        self.assertIn("category", errors)
        self.assertIn("location", errors)
        self.assertIn("date", errors)
        self.assertIn("description", errors)

        # Future date should fail
        errors = _validate_item_form({
            "name": "Laptop",
            "category": "Laptop",
            "location": "Library",
            "date": "2099-01-01",
            "description": "Silver Dell laptop with stickers"
        })
        self.assertIn("date", errors)
        self.assertIn("future", errors["date"].lower())

        # Valid form should pass
        errors = _validate_item_form({
            "name": "Black Umbrella",
            "category": "Other",
            "location": "Main Entrance",
            "date": "2026-09-18",
            "description": "Foldable black umbrella left near door"
        })
        self.assertEqual(errors, {})

    def test_data_adapter_operations(self):
        """Test core database adapter methods."""
        # 1. Organizations
        orgs = db.get_all_orgs()
        self.assertTrue(len(orgs) >= 2)
        vsb = db.get_org("org-001")
        self.assertEqual(vsb["name"], "VSB Engineering College")

        # 2. Add and retrieve reports
        lost_item = {
            "id": db.next_id("lost"),
            "org_id": "org-001",
            "user_id": "user-001",
            "name": "Integration Test Notebook",
            "category": "Books",
            "location": "Hall 3",
            "date": "2026-09-18",
            "description": "Blue ruled spiral notebook",
            "status": "Searching"
        }
        saved_lost = db.add_lost_report(lost_item)
        self.assertEqual(saved_lost["name"], "Integration Test Notebook")

        # Lookup polymorphism
        found_lookup = db.get_item(saved_lost["id"])
        self.assertIsNotNone(found_lookup)
        self.assertEqual(found_lookup["name"], "Integration Test Notebook")

        # 3. Admin stats calculation
        stats = db.admin_stats("org-001")
        self.assertIn("total_users", stats)
        self.assertIn("return_rate", stats)
        self.assertIsInstance(stats["return_rate"], (int, float))

    def test_handover_flow(self):
        """Test complete handover lifecycle: claim -> review -> approval -> return."""
        lost = {
            "id": db.next_id("lost"), "org_id": "org-001", "user_id": "user-001",
            "name": "Test Backpack", "category": "Bag", "location": "Gym",
            "date": "2026-09-18", "description": "Black Nike backpack", "status": "Possible Match"
        }
        found = {
            "id": db.next_id("found"), "org_id": "org-001", "user_id": "user-002",
            "name": "Test Backpack Found", "category": "Bag", "location": "Gym",
            "date": "2026-09-18", "description": "Black backpack found in gym", "status": "Possible Match"
        }
        db.add_lost_report(lost)
        db.add_found_report(found)
        match = db.add_match(lost, found, 85, {"Same category": 20, "Location": 10})

        # Submit claim
        ok = db.submit_ownership_claim(match["id"], lost["id"], "user-001", "There is a blue gym pass inside.")
        self.assertTrue(ok)
        m = db.get_match(match["id"])
        self.assertEqual(m["claim_status"], "pending")

        # Staff approval
        ok_decide = db.decide_ownership_claim(match["id"], "approve", reviewer_id="user-002")
        self.assertTrue(ok_decide)
        m_app = db.get_match(match["id"])
        self.assertEqual(m_app["claim_status"], "approved")

        # Mark returned
        ok_ret = db.mark_item_returned(found["id"])
        self.assertTrue(ok_ret)
        f_ret = db.get_item(found["id"])
        self.assertEqual(f_ret["status"], "Returned")


if __name__ == "__main__":
    unittest.main()
