import re

filepath = 'api/migrations/0067_unit_client_is_deleted_client_version_and_more.py'

with open(filepath, 'r') as f:
    content = f.read()

# We only want to keep migrations that are NOT AlterField for id or created_at
# Look at operations list.
# A regex to match block of AlterField for created_at or id:
pattern = r"        migrations\.AlterField\(\s*model_name='[^']+',\s*name='(created_at|id)',\s*field=[^,]+,\s*\),\n"
# Actually the regex might be slightly different because there are multiple lines.
# Instead, let's just parse the python file content manually.

lines = content.split('\n')
new_lines = []
in_alter = False
for line in lines:
    if "migrations.AlterField(" in line:
        in_alter = True
        temp_buffer = [line]
    elif in_alter:
        temp_buffer.append(line)
        if ")," in line and line.strip() == "),":
            in_alter = False
            block = "\n".join(temp_buffer)
            # If it alters created_at or id, skip it.
            if "'created_at'" in block or "'id'" in block:
                pass # skip
            else:
                new_lines.extend(temp_buffer)
    else:
        new_lines.append(line)

new_content = "\n".join(new_lines)
with open(filepath, 'w') as f:
    f.write(new_content)

print(f"Removed {len(lines) - len(new_lines)} lines of AlterField")
