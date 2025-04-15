from django.test import TestCase
from django.db import connections
from django.db.utils import OperationalError
import psycopg2
from .models import Machine, Warning, Telemetry, WarningRule
from django.contrib.auth.models import User

class PostgreSQLConnectionTestCase(TestCase):
    """Test cases for PostgreSQL database connection."""
    
    def test_django_postgresql_connection(self):
        """Test PostgreSQL connection using Django's connection mechanism."""
        try:
            db_conn = connections['default']
            db_conn.cursor()
            self.assertTrue(True, "Successfully connected to PostgreSQL through Django")
        except OperationalError as e:
            self.fail(f"Unable to connect to PostgreSQL database through Django: {e}")
    
    def test_direct_postgresql_connection(self):
        """Test PostgreSQL connection directly using psycopg2."""
        try:
            # Get connection parameters from settings
            db_settings = connections['default'].settings_dict
            
            connection = psycopg2.connect(
                host=db_settings.get('HOST', 'localhost'),
                database=db_settings.get('NAME', 'postgres'),
                user=db_settings.get('USER', 'postgres'),
                password=db_settings.get('PASSWORD', 'postgres'),
                port=db_settings.get('PORT', '5432')
            )
            
            cursor = connection.cursor()
            cursor.execute("SELECT version();")
            db_version = cursor.fetchone()
            
            print(f"PostgreSQL version: {db_version[0]}")
            
            # Close the cursor and connection
            cursor.close()
            connection.close()
            
            self.assertTrue(True, "Successfully connected directly to PostgreSQL")
            
        except (Exception, psycopg2.Error) as error:
            self.fail(f"Error connecting to PostgreSQL: {error}")

class MachineCreationTestCase(TestCase):
    def setUp(self):
        # Set up any initial data if needed
        pass

    def test_machine_creation(self):
        # Create a machine instance with all required fields
        machine = Machine.objects.create(
            name="Test Machine",
            status="operational",
            installation_date="2025-04-15",  # Required field
            serial_number="SN12345",  # Added unique serial number
            model="Model X",  # Added model
            manufacturer="Manufacturer Y"  # Added manufacturer
        )

        # Assert that the machine was created successfully
        self.assertIsNotNone(machine.id)
        self.assertEqual(machine.name, "Test Machine")
        self.assertEqual(machine.status, "operational")
        self.assertEqual(machine.installation_date, "2025-04-15")
        self.assertEqual(machine.serial_number, "SN12345")
        self.assertEqual(machine.model, "Model X")
        self.assertEqual(machine.manufacturer, "Manufacturer Y")

class WarningModelTestCase(TestCase):
    def setUp(self):
        # Create a user for testing
        self.user = User.objects.create_user(username="testuser", password="password")

        # Create a machine for testing
        self.machine = Machine.objects.create(
            name="Test Machine",
            serial_number="SN12345",
            model="Model X",
            manufacturer="Manufacturer Y",
            status="operational",
            installation_date="2025-04-01"
        )

        # Create a warning rule for testing
        self.warning_rule = WarningRule.objects.create(
            name="High Temperature",
            parameter="temperature",
            comparison_operator=">",
            threshold_value=80.0,
            severity="high",
            created_by=self.user
        )

        # Create telemetry data for testing
        self.telemetry = Telemetry.objects.create(
            machine=self.machine,
            parameter="temperature",
            value=85.0
        )

    def test_warning_creation(self):
        # Create a warning based on the telemetry and rule
        warning = Warning.objects.create(
            machine=self.machine,
            rule=self.warning_rule,
            telemetry=self.telemetry,
            description="Temperature exceeded threshold."
        )

        # Assert the warning was created correctly
        self.assertEqual(warning.machine, self.machine)
        self.assertEqual(warning.rule, self.warning_rule)
        self.assertEqual(warning.telemetry, self.telemetry)
        self.assertEqual(warning.description, "Temperature exceeded threshold.")
        self.assertTrue(warning.is_active)

class TelemetryModelTestCase(TestCase):
    def setUp(self):
        # Create a machine for testing
        self.machine = Machine.objects.create(
            name="Test Machine",
            serial_number="SN12345",
            model="Model X",
            manufacturer="Manufacturer Y",
            status="operational",
            installation_date="2025-04-01"
        )

    def test_telemetry_creation(self):
        # Create telemetry data
        telemetry = Telemetry.objects.create(
            machine=self.machine,
            parameter="temperature",
            value=75.0
        )

        # Assert the telemetry data was created correctly
        self.assertEqual(telemetry.machine, self.machine)
        self.assertEqual(telemetry.parameter, "temperature")
        self.assertEqual(telemetry.value, 75.0)
