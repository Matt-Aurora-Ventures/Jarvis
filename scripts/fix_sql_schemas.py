import re
import os

SCHEMA_FILES = [
    '.planning/phases/01-database-consolidation/jarvis_analytics_schema.sql',
    '.planning/phases/01-database-consolidation/jarvis_cache_schema.sql'
]

def fix_schema_file(filepath):
    print(f"Fixing {filepath}...")
    with open(filepath, 'r') as f:
        content = f.read()

    # Find the current table name being defined
    # We iterate line by line to track context
    lines = content.split('\n')
    new_lines = []
    indexes_to_create = []
    current_table = None

    for line in lines:
        # Check for CREATE TABLE
        table_match = re.search(r'CREATE TABLE IF NOT EXISTS (\w+)', line, re.IGNORECASE)
        if table_match:
            current_table = table_match.group(1)
            new_lines.append(line)
            continue

        # Check for inline INDEX
        # Pattern: INDEX index_name (column_name)
        # We need to remove the comma from the previous line if this is the last item
        index_match = re.search(r'^\s*INDEX\s+(\w+)\s*\((.+)\)(,?)\s*$', line, re.IGNORECASE)
        
        if index_match:
            if not current_table:
                print(f"❌ Error: Found INDEX outside of table definition! Line: {line}")
                new_lines.append(line)
                continue
                
            index_name = index_match.group(1)
            columns = index_match.group(2)
            
            indexes_to_create.append(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON {current_table}({columns});"
            )
            
            # Remove this line
            # Also need to handle comma on previous line
            if new_lines and new_lines[-1].rstrip().endswith(','):
                new_lines[-1] = new_lines[-1].rstrip().rstrip(',')
            continue
            
        new_lines.append(line)
    
    # Reassemble content
    fixed_content = '\n'.join(new_lines)
    
    # Append created indexes at the end (or after the table? usually after table is better layout, but appending is safer)
    # Actually, appending after each table block is best, but appending all at end is valid SQL.
    # Let's append all indexes at the end of the file or after the table definition?
    # Simple approach: Append all indexes just before "MIGRATION NOTES" or at the end.
    
    # Better: Insert them right after the table definition closing parenthesis?
    # Too complex parsing. Let's just append them to the end of the file before comments.
    
    # Check if we are inside a CREATE TABLE block... complex.
    # Let's just append all collected indexes at the end of the file.
    
    if indexes_to_create:
        fixed_content += "\n\n-- ============================================================================\n"
        fixed_content += "-- FIXED INDEXES (Moved from inline)\n"
        fixed_content += "-- ============================================================================\n\n"
        fixed_content += '\n'.join(indexes_to_create) + "\n"
        
    with open(filepath, 'w') as f:
        f.write(fixed_content)
    
    print(f"✅ Fixed {len(indexes_to_create)} indexes in {filepath}")

for f in SCHEMA_FILES:
    if os.path.exists(f):
        fix_schema_file(f)
    else:
        print(f"⚠️ File not found: {f}")
