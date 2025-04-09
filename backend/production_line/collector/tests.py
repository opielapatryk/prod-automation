from django.test import TestCase
from django.db import connections
from django.db.utils import OperationalError
import psycopg2

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
