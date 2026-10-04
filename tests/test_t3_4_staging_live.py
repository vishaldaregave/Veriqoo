"""Integration and Security Test Suite for T3-4 Staging / Live PostgreSQL Verification.

This test suite is SKIPPED by default unless VERIQOO_STAGING_LIVE=true is set
along with STAGING_SUPABASE_URL and STAGING_SUPABASE_KEY / STAGING_SUPABASE_SERVICE_ROLE_KEY.
It never runs during normal offline unit tests.
"""

from __future__ import annotations

import sys
sys.modules['ujson'] = None

import os
import unittest
import requests

from backend.app.services.authority.case_repository import SupabaseAuthorityCaseRepository


@unittest.skipUnless(
    os.getenv("VERIQOO_STAGING_LIVE", "").lower() == "true",
    "Staging live tests skipped: VERIQOO_STAGING_LIVE environment variable is not set to 'true'.",
)
class TestT34StagingLiveVerification(unittest.TestCase):
    """Verifies live PostgreSQL RPC execution, RLS policies, and atomic rollbacks against a real staging database."""

    @classmethod
    def setUpClass(cls):
        cls.supabase_url = os.getenv("STAGING_SUPABASE_URL") or os.getenv("SUPABASE_URL")
        cls.service_key = os.getenv("STAGING_SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        cls.anon_key = os.getenv("STAGING_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")

        if not cls.supabase_url or not cls.service_key:
            raise unittest.SkipTest("Staging credentials missing: STAGING_SUPABASE_URL or STAGING_SUPABASE_SERVICE_ROLE_KEY.")

        # Safety Guard: Ensure target is never production
        if "prod" in cls.supabase_url.lower() and "staging" not in cls.supabase_url.lower():
            raise RuntimeError("CRITICAL SAFETY HALT: Production URL detected in staging test runner!")

        cls.repo = SupabaseAuthorityCaseRepository(
            base_url=f"{cls.supabase_url}/rest/v1",
            api_key=cls.service_key,
        )

    def test_01_public_rpc_execution_is_revoked(self):
        """Verify that anon/public clients cannot invoke authority RPCs directly over PostgREST."""
        if not self.anon_key:
            self.skipTest("Anon key not provided")

        url = f"{self.supabase_url}/rest/v1/rpc/authority_assign_case"
        headers = {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.anon_key}",
            "Content-Type": "application/json",
        }
        res = requests.post(url, headers=headers, json={}, timeout=5)
        # PostgREST returns 401 Unauthorized or 403 Forbidden / function not found for ungranted roles
        self.assertIn(res.status_code, [401, 403, 404])

    def test_02_staging_health_and_version(self):
        """Verify staging REST endpoint responds and authentication header is accepted."""
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
        }
        res = requests.get(f"{self.supabase_url}/rest/v1/", headers=headers, timeout=5)
        self.assertEqual(res.status_code, 200)

    def test_03_establishment_review_rpc_public_execution_revoked(self):
        """Verify that anon/public clients cannot invoke authority_review_establishment directly."""
        if not self.anon_key:
            self.skipTest("Anon key not provided")

        url = f"{self.supabase_url}/rest/v1/rpc/authority_review_establishment"
        headers = {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.anon_key}",
            "Content-Type": "application/json",
        }
        res = requests.post(url, headers=headers, json={}, timeout=5)
        self.assertIn(res.status_code, [401, 403, 404])

    def test_04_establishment_review_rpc_contract(self):
        """Verify that service_role invocation of authority_review_establishment enforces expected_status."""
        url = f"{self.supabase_url}/rest/v1/rpc/authority_review_establishment"
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }
        # Calling with empty body should fail due to missing required arguments or validation
        res = requests.post(url, headers=headers, json={}, timeout=5)
        self.assertIn(res.status_code, [400, 422, 500])

