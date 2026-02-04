# test_firebird.py (supervisor/ klasöründe)

from services.firebird_service import FirebirdService

# Test
fb = FirebirdService()
result = fb.create_database('TEST123', 'TEST_DB. FDB')

print(result)