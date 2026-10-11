"""
Unit tests for ZuvioAutoChecker class
"""

import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os

# Add parent directory to path to import main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import ZuvioAutoChecker, UserCredentials, AuthToken, Location, CourseService


class TestZuvioAutoChecker(unittest.TestCase):
    """Test cases for ZuvioAutoChecker class"""
    
    def setUp(self):
        """Set up test fixtures"""
        with patch('main.ConfigManager'), \
             patch('main.AuthService'):
            self.checker = ZuvioAutoChecker()
    
    def test_init(self):
        """Test ZuvioAutoChecker initialization"""
        self.assertIsNotNone(self.checker.config_manager)
        self.assertIsNotNone(self.checker.auth_service)
        self.assertIsNone(self.checker.course_service)
        self.assertTrue(self.checker.running)
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_setup_user_credentials_new_user(self, mock_print, mock_input):
        """Test setting up credentials for new user"""
        mock_input.side_effect = ['test@example.com', 'password123']
        
        with patch.object(self.checker.config_manager, 'get_user_credentials', return_value=None), \
             patch.object(self.checker.config_manager, 'save_user_credentials') as mock_save:
            
            credentials = self.checker.setup_user_credentials()
            
            self.assertEqual(credentials.account, 'test@example.com')
            self.assertEqual(credentials.password, 'password123')
            mock_save.assert_called_once()
    
    def test_setup_user_credentials_existing_user(self):
        """Test setting up credentials for existing user"""
        existing_credentials = UserCredentials(account='existing@example.com', password='existingpass')
        
        with patch.object(self.checker.config_manager, 'get_user_credentials', return_value=existing_credentials):
            credentials = self.checker.setup_user_credentials()
            
            self.assertEqual(credentials.account, 'existing@example.com')
            self.assertEqual(credentials.password, 'existingpass')
    
    def test_test_login_and_setup_success_first_attempt(self):
        """Test successful login on first attempt"""
        credentials = UserCredentials(account='test@example.com', password='password123')
        auth_token = AuthToken(user_id='12345', access_token='abc123')
        
        with patch.object(self.checker.auth_service, 'login', return_value=auth_token), \
             patch('builtins.print') as mock_print:
            
            result = self.checker.test_login_and_setup(credentials)
            
            self.assertEqual(result, auth_token)
            mock_print.assert_called_with("登入測試成功！")
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_test_login_and_setup_retry_success(self, mock_print, mock_input):
        """Test successful login after retry"""
        credentials = UserCredentials(account='test@example.com', password='password123')
        auth_token = AuthToken(user_id='12345', access_token='abc123')
        
        mock_input.return_value = 'y'
        
        with patch.object(self.checker.auth_service, 'login') as mock_login, \
             patch.object(self.checker.config_manager, 'save_user_credentials'):
            
            # First attempt fails, second succeeds
            mock_login.side_effect = [None, auth_token]
            
            result = self.checker.test_login_and_setup(credentials)
            
            self.assertEqual(result, auth_token)
            self.assertEqual(mock_login.call_count, 2)
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_test_login_and_setup_max_attempts_exceeded(self, mock_print, mock_input):
        """Test login failure after max attempts"""
        credentials = UserCredentials(account='test@example.com', password='password123')
        
        mock_input.return_value = 'y'
        
        with patch.object(self.checker.auth_service, 'login', return_value=None), \
             patch.object(self.checker.config_manager, 'save_user_credentials'):
            
            result = self.checker.test_login_and_setup(credentials)
            
            self.assertIsNone(result)
            mock_print.assert_called_with("已達到最大嘗試次數，登入失敗")
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_setup_location_new_location(self, mock_print, mock_input):
        """Test setting up new location"""
        mock_input.side_effect = ['120.123', '22.456']
        
        with patch.object(self.checker.config_manager, 'get_location', return_value=None), \
             patch.object(self.checker.config_manager, 'save_location') as mock_save:
            
            location = self.checker.setup_location()
            
            self.assertEqual(location.longitude, '120.123')
            self.assertEqual(location.latitude, '22.456')
            mock_save.assert_called_once()
    
    def test_setup_location_existing_location(self):
        """Test setup with existing location"""
        existing_location = Location(latitude='22.123', longitude='120.456')
        
        with patch.object(self.checker.config_manager, 'get_location', return_value=existing_location):
            location = self.checker.setup_location()
            
            self.assertEqual(location.latitude, '22.123')
            self.assertEqual(location.longitude, '120.456')
    
    @patch('builtins.print')
    def test_display_courses(self, mock_print):
        """Test displaying course list"""
        courses = [
            {'course_name': 'Course 1', 'teacher_name': 'Teacher 1'},
            {'course_name': 'Course 2', 'teacher_name': 'Teacher 2'}
        ]
        
        with patch('main.datetime') as mock_datetime:
            mock_datetime.today.return_value.strftime.return_value = '2024/01/01'
            
            self.checker.display_courses(courses)
            
            # Should print date and course information
            self.assertTrue(mock_print.called)
    
    def test_run_checkin_loop_with_available_course(self):
        """An open rollcall is checked in only after the five-second delay."""
        auth_token = AuthToken(user_id='12345', access_token='abc123')
        location = Location(latitude='22.123', longitude='120.456')
        courses = [{'course_name': 'Test Course', 'course_id': 'course1'}]
        self.checker.course_service = MagicMock(spec=CourseService)
        self.checker.course_service.check_rollcall_availability.return_value = 'rollcall123'
        waited = False

        def wait(seconds):
            nonlocal waited
            if seconds == 5:
                waited = True
            else:
                self.checker.running = False

        def checkin(*args):
            self.assertTrue(waited)
            return True, "簽到成功！"

        self.checker.course_service.perform_checkin.side_effect = checkin
        with patch('builtins.print'), \
             patch('main.random.randint', return_value=1), \
             patch('main.time.sleep', side_effect=wait) as mock_sleep:
            self.checker.run_checkin_loop(auth_token, courses, location)

        self.assertEqual(mock_sleep.call_args_list, [call(5), call(1)])
        self.assertEqual(self.checker.course_service.check_rollcall_availability.call_count, 2)
        self.checker.course_service.perform_checkin.assert_called_once_with(
            auth_token, 'rollcall123', location
        )

    def test_run_checkin_loop_no_available_courses(self):
        """Test check-in loop with no available courses"""
        auth_token = AuthToken(user_id='12345', access_token='abc123')
        location = Location(latitude='22.123', longitude='120.456')
        courses = [{'course_name': 'Test Course', 'course_id': 'course1'}]
        self.checker.course_service = MagicMock(spec=CourseService)
        self.checker.course_service.check_rollcall_availability.return_value = None

        def stop_loop(seconds):
            self.checker.running = False

        with patch('main.random.randint', return_value=1), \
             patch('builtins.print'), \
             patch('main.time.sleep', side_effect=stop_loop) as mock_sleep:
            self.checker.run_checkin_loop(auth_token, courses, location)

        mock_sleep.assert_called_once_with(1)
        self.checker.course_service.perform_checkin.assert_not_called()

    def test_run_checkin_loop_rollcall_closes_or_changes_during_delay(self):
        """A closed or replaced rollcall is skipped, and a later one can succeed."""
        auth_token = AuthToken(user_id='12345', access_token='abc123')
        location = Location(latitude='22.123', longitude='120.456')
        courses = [{'course_name': 'Test Course', 'course_id': 'course1'}]

        for delayed_rollcall_id in (None, 'replacement123'):
            with self.subTest(delayed_rollcall_id=delayed_rollcall_id):
                self.checker.running = True
                service = MagicMock(spec=CourseService)
                self.checker.course_service = service
                service.check_rollcall_availability.return_value = 'rollcall123'
                service.perform_checkin.return_value = (True, "簽到成功！")
                poll_count = 0

                def wait(seconds):
                    nonlocal poll_count
                    if seconds == 5 and poll_count == 0:
                        service.check_rollcall_availability.return_value = delayed_rollcall_id
                    elif seconds == 1:
                        poll_count += 1
                        if poll_count == 1:
                            service.perform_checkin.assert_not_called()
                            service.check_rollcall_availability.return_value = 'later123'
                        else:
                            self.checker.running = False

                with patch('main.random.randint', return_value=1), \
                     patch('builtins.print') as mock_print, \
                     patch('main.time.sleep', side_effect=wait):
                    self.checker.run_checkin_loop(auth_token, courses, location)

                mock_print.assert_any_call("Test Course - 簽到已關閉或變更，略過此次簽到")
                service.perform_checkin.assert_called_once_with(auth_token, 'later123', location)

    def test_run_checkin_loop_failed_checkin_keeps_monitoring(self):
        """A server rejection after the delay does not prevent a later check-in."""
        auth_token = AuthToken(user_id='12345', access_token='abc123')
        location = Location(latitude='22.123', longitude='120.456')
        courses = [{'course_name': 'Test Course', 'course_id': 'course1'}]
        service = MagicMock(spec=CourseService)
        self.checker.course_service = service
        service.check_rollcall_availability.return_value = 'rollcall123'
        service.perform_checkin.side_effect = [(False, "簽到已結束"), (True, "簽到成功！")]

        def wait(seconds):
            if seconds == 1:
                if service.perform_checkin.call_count == 1:
                    service.check_rollcall_availability.return_value = 'later123'
                else:
                    self.checker.running = False

        with patch('main.random.randint', return_value=1), \
             patch('builtins.print') as mock_print, \
             patch('main.time.sleep', side_effect=wait):
            self.checker.run_checkin_loop(auth_token, courses, location)

        mock_print.assert_any_call("Test Course - 簽到已結束")
        self.assertEqual(service.perform_checkin.call_args_list, [
            call(auth_token, 'rollcall123', location),
            call(auth_token, 'later123', location)
        ])


if __name__ == '__main__':
    unittest.main()
