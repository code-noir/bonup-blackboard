# backend/api/tests/test_bonid_lifetime.py
#
# Tests for the bonID lifetime rule:
#   - Once assigned, a bonID is never reused.
#   - Deactivation keeps the bonID attached.
#   - Hard deletion retires the bonID in the ledger.
#   - Future generation consults the ledger, not just living profiles.

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.users.models import AssignedBonId, BonUserProfile, ReservedBonId

User = get_user_model()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_user(email, password="TestPass123!"):
    """Create a user using the email-as-username identity model."""
    return User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name="Test",
        last_name="User",
    )


def _clear_bonid_tables():
    """
    Wipe all bonID-related rows for clean-state tests.
    Safe within TestCase (all writes are inside the test transaction and
    rolled back at the end of the test).

    Deletion order matters:
      1. AssignedBonId first — the pre_delete signal on BonUserProfile does
         an UPDATE on AssignedBonId; if AssignedBonId is already empty the
         signal update is a harmless no-op.
      2. User.objects.all().delete() — CASCADEs into BonUserProfile, firing
         pre_delete signals (which are no-ops because step 1 already cleared
         AssignedBonId).
      3. ReservedBonId — clear binary-reserved rows so the sequence can
         restart from scratch.
    """
    AssignedBonId.objects.all().delete()
    User.objects.all().delete()
    ReservedBonId.objects.all().delete()


# ---------------------------------------------------------------------------
# 1. Clean-state sequence
# ---------------------------------------------------------------------------

class BonIdCleanStateTests(TestCase):

    def test_first_bonid_on_clean_state_is_0000000000002(self):
        """
        On an entirely empty system the first real bonID must be 0000000000002.
        0000000000000 and 0000000000001 are binary-reserved and must be skipped.
        """
        _clear_bonid_tables()

        user = _make_user("first@example.com")
        self.assertEqual(user.bon_profile.bon_id, "0000000000002")

    def test_binary_only_candidates_are_skipped_and_reserved(self):
        """
        0000000000000, 0000000000001 must be written to ReservedBonId and
        skipped.  The first three assigned bonIDs on a clean system are
        0000000000002, 0000000000003, 0000000000004.
        """
        _clear_bonid_tables()

        u1 = _make_user("a@example.com")
        u2 = _make_user("b@example.com")
        u3 = _make_user("c@example.com")

        self.assertEqual(u1.bon_profile.bon_id, "0000000000002")
        self.assertEqual(u2.bon_profile.bon_id, "0000000000003")
        self.assertEqual(u3.bon_profile.bon_id, "0000000000004")

        # 0 and 1 must now be in ReservedBonId
        self.assertTrue(ReservedBonId.objects.filter(bon_id="0000000000000").exists())
        self.assertTrue(ReservedBonId.objects.filter(bon_id="0000000000001").exists())

    def test_binary_gap_at_11_is_skipped(self):
        """
        0000000000011 (contains only 0 and 1) must be reserved and skipped.
        The sequence should jump from 0000000000010 to 0000000000012.

        NOTE: 0000000000010 is also binary-only (chars {0,1}) and will itself
        be skipped.  The sequence around this range on a clean system:
          ...0000000000008, 0000000000009, 0000000000012...
        (010 and 011 are both skipped).
        """
        _clear_bonid_tables()

        # Create enough users to push past position 11
        ids = []
        for i in range(12):
            u = _make_user(f"seq{i}@example.com")
            ids.append(u.bon_profile.bon_id)

        # Binary-only candidates in range 0-13: 0,1,10,11
        binary_reserved = {"0000000000000", "0000000000001", "0000000000010", "0000000000011"}
        for val in binary_reserved:
            self.assertNotIn(val, ids, f"{val} must not be assigned — it is binary-reserved")

        # Sequence must still be contiguous (excluding reserved)
        for val in ids:
            self.assertFalse(
                BonUserProfile.is_reserved_bon_id(val),
                f"Assigned bonID {val} is binary-reserved — should never be issued",
            )


# ---------------------------------------------------------------------------
# 2. Ledger write at assignment
# ---------------------------------------------------------------------------

class BonIdLedgerWriteTests(TestCase):

    def test_new_bonid_assignment_creates_ledger_row(self):
        """Creating a user must produce exactly one AssignedBonId row."""
        before = AssignedBonId.objects.count()
        user = _make_user("ledger@example.com")
        after = AssignedBonId.objects.count()

        self.assertEqual(after, before + 1)
        self.assertTrue(
            AssignedBonId.objects.filter(bon_id=user.bon_profile.bon_id).exists()
        )

    def test_ledger_row_has_status_active(self):
        user = _make_user("active@example.com")
        entry = AssignedBonId.objects.get(bon_id=user.bon_profile.bon_id)
        self.assertEqual(entry.status, AssignedBonId.STATUS_ACTIVE)

    def test_ledger_row_captures_identity_snapshot(self):
        """Identity snapshot fields must be populated at assignment time."""
        user = _make_user("snapshot@example.com")
        entry = AssignedBonId.objects.get(bon_id=user.bon_profile.bon_id)

        self.assertEqual(entry.email_snapshot, "snapshot@example.com")
        self.assertEqual(entry.first_name_snapshot, "Test")
        self.assertEqual(entry.last_name_snapshot, "User")
        self.assertEqual(entry.user_id_at_assignment, user.pk)

    def test_ledger_row_retired_at_is_null_on_active(self):
        user = _make_user("nullretired@example.com")
        entry = AssignedBonId.objects.get(bon_id=user.bon_profile.bon_id)
        self.assertIsNone(entry.retired_at)
        self.assertIsNone(entry.retirement_reason)

    def test_profile_update_does_not_create_extra_ledger_row(self):
        """Saving the profile a second time (update) must not add a new ledger row."""
        user = _make_user("nodouble@example.com")
        profile = user.bon_profile
        before = AssignedBonId.objects.count()

        profile.city = "Port-au-Prince"
        profile.save()

        after = AssignedBonId.objects.count()
        self.assertEqual(after, before)


# ---------------------------------------------------------------------------
# 3. Deactivation
# ---------------------------------------------------------------------------

class BonIdDeactivationTests(TestCase):

    def test_deactivation_preserves_bonid(self):
        """
        Setting User.is_active=False must not change the bonID or remove
        the BonUserProfile row.
        """
        user = _make_user("deactivate@example.com")
        original_bon_id = user.bon_profile.bon_id

        user.is_active = False
        user.save()

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(user.bon_profile.bon_id, original_bon_id)

    def test_deactivation_does_not_retire_ledger_row(self):
        """
        Soft-deactivation leaves the AssignedBonId ledger row status=active.
        The bonID remains attached to the account and can be restored by
        re-activating the user.
        """
        user = _make_user("softclose@example.com")
        bon_id = user.bon_profile.bon_id

        user.is_active = False
        user.save()

        entry = AssignedBonId.objects.get(bon_id=bon_id)
        self.assertEqual(entry.status, AssignedBonId.STATUS_ACTIVE)
        self.assertIsNone(entry.retired_at)


# ---------------------------------------------------------------------------
# 4. Hard deletion
# ---------------------------------------------------------------------------

class BonIdHardDeleteTests(TestCase):

    def test_hard_delete_marks_ledger_row_retired(self):
        """Deleting a User must set the ledger entry to status=retired."""
        user = _make_user("harddelete@example.com")
        bon_id = user.bon_profile.bon_id

        user.delete()

        entry = AssignedBonId.objects.get(bon_id=bon_id)
        self.assertEqual(entry.status, AssignedBonId.STATUS_RETIRED)
        self.assertIsNotNone(entry.retired_at)
        self.assertEqual(entry.retirement_reason, AssignedBonId.REASON_HARD_DELETED)

    def test_hard_delete_preserves_identity_snapshot(self):
        """
        The identity snapshot (email, names) must survive deletion so the
        ledger can be used for historical auditing and account restoration.
        """
        user = _make_user("snapshot_del@example.com")
        bon_id = user.bon_profile.bon_id

        user.delete()

        entry = AssignedBonId.objects.get(bon_id=bon_id)
        self.assertEqual(entry.email_snapshot, "snapshot_del@example.com")
        self.assertEqual(entry.first_name_snapshot, "Test")
        self.assertEqual(entry.last_name_snapshot, "User")

    def test_hard_deleted_bonid_not_reissued(self):
        """
        After hard-deleting a user, the next registration must receive a
        strictly higher bonID — the deleted bonID must not be reissued.
        """
        user_a = _make_user("del_a@example.com")
        bon_id_a = user_a.bon_profile.bon_id

        user_a.delete()

        user_b = _make_user("del_b@example.com")
        bon_id_b = user_b.bon_profile.bon_id

        self.assertNotEqual(bon_id_b, bon_id_a)
        self.assertGreater(int(bon_id_b), int(bon_id_a))

    def test_profile_delete_also_retires_ledger(self):
        """
        Direct BonUserProfile deletion (not via User CASCADE) must also
        mark the ledger row as retired.
        """
        user = _make_user("profiledel@example.com")
        bon_id = user.bon_profile.bon_id

        user.bon_profile.delete()

        entry = AssignedBonId.objects.get(bon_id=bon_id)
        self.assertEqual(entry.status, AssignedBonId.STATUS_RETIRED)


# ---------------------------------------------------------------------------
# 5. Ledger as sequence source
# ---------------------------------------------------------------------------

class BonIdLedgerSequenceTests(TestCase):

    def test_generation_uses_ledger_not_only_living_profiles(self):
        """
        After hard-deleting a user, the remaining retired ledger entry must
        prevent the sequence from going backwards.  A new registration must
        receive a bonID strictly higher than the deleted user's bonID.
        """
        user_a = _make_user("seq_a@example.com")
        bon_id_a = user_a.bon_profile.bon_id

        user_a.delete()

        # BonUserProfile row for A is gone.
        self.assertFalse(BonUserProfile.objects.filter(bon_id=bon_id_a).exists())

        # AssignedBonId row for A still exists (retired).
        self.assertTrue(AssignedBonId.objects.filter(bon_id=bon_id_a).exists())

        user_b = _make_user("seq_b@example.com")
        bon_id_b = user_b.bon_profile.bon_id

        self.assertGreater(int(bon_id_b), int(bon_id_a))

    def test_sequence_continues_correctly_after_multiple_deletions(self):
        """
        Deleting multiple users and then registering a new one must still
        produce a strictly increasing bonID relative to the highest ever assigned.
        """
        users = [_make_user(f"multi{i}@example.com") for i in range(3)]
        highest = max(int(u.bon_profile.bon_id) for u in users)

        for u in users:
            u.delete()

        new_user = _make_user("new_after_purge@example.com")
        new_bon_id = int(new_user.bon_profile.bon_id)

        self.assertGreater(new_bon_id, highest)

    def test_retired_ledger_entries_count_toward_max(self):
        """
        Retired entries in AssignedBonId must be counted toward the sequence
        maximum so they can never be re-examined by the generator.
        """
        user = _make_user("max_test@example.com")
        bon_id = int(user.bon_profile.bon_id)
        user.delete()

        # Next generation must start from bon_id + 1 (or higher for binary gaps)
        next_user = _make_user("max_test_next@example.com")
        next_bon_id = int(next_user.bon_profile.bon_id)

        self.assertGreater(next_bon_id, bon_id)
