from django.test import TestCase
from django.db import connections
from django.db.utils import OperationalError
import psycopg2
from .models import Machine

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
