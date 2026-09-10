import unittest
from unittest.mock import MagicMock

from app.repositories.reports import MySqlReportRepository, ReportNotReadyError


class JiraRetryTest(unittest.TestCase):
    def repository(self, rows):
        database = MagicMock()
        cursor = database.connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = rows
        return MySqlReportRepository(database), cursor

    def test_failed_job_is_requeued_with_current_initial_audit(self):
        repository, cursor = self.repository([
            {'id': 1, 'jira_id': None, 'jira_status': 'error'},
            {'version_id': 3, 'audit_id': 7},
        ])
        self.assertTrue(repository.retry_jira_creation(1)['created'])
        sql, params = cursor.execute.call_args.args
        self.assertIn('jira_attempts = 0', sql)
        self.assertEqual(params, [3, 7, 1])

    def test_active_or_created_job_is_not_requeued(self):
        for status in ('pending', 'creating', 'created'):
            repository, cursor = self.repository([
                {'id': 1, 'jira_id': None, 'jira_status': status},
            ])
            self.assertFalse(repository.retry_jira_creation(1)['created'])
            self.assertEqual(cursor.execute.call_count, 1)

    def test_initial_not_passed_is_rejected(self):
        repository, cursor = self.repository([
            {'id': 1, 'jira_id': None, 'jira_status': 'error'}, None,
        ])
        with self.assertRaises(ReportNotReadyError):
            repository.retry_jira_creation(1)
        self.assertEqual(cursor.execute.call_count, 2)

    def test_missing_report(self):
        repository, _ = self.repository([None])
        self.assertIsNone(repository.retry_jira_creation(1))
