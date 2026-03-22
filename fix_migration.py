import re

filepath = 'api/migrations/0067_unit_client_is_deleted_client_version_and_more.py'

with open(filepath, 'r') as f:
    content = f.read()

# Regex to match AlterField operations for 'created_at' and 'id'
# E.g. migrations.AlterField(model_name='client', name='created_at', ...),
pattern = r"        migrations\.AlterField\(\s*model_name='[^']+',\s*name='(created_at|id)',(?:[^)]+\)){2},\n"

# Remove them
new_content = re.sub(pattern, '', content)

with open(filepath, 'w') as f:
    f.write(new_content)

print("Unnecessary AlterFields removed.")
