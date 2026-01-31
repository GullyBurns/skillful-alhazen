__all__ = ['sqla_source_code', 'source', 'target', 'classes_to_edit', 'raw_sql_source_code', 'lines']

import os
import re
import local_resources.linkml as linkml
from importlib_resources import files

sqla_source_code = files(linkml).joinpath('schema_sqla.py').read_text()

source = '''has_notes = relationship\( "Note", secondary="Note_has_notes"\)'''
target = '''has_notes = relationship( "Note", 
                             secondary="Note_has_notes", 
                             primaryjoin="Note.id==Note_has_notes.c.Note_id",
                             secondaryjoin="Note.id==Note_has_notes.c.has_notes_id",
                             back_populates="is_about")'''
if re.search(source, sqla_source_code):
    sqla_source_code = re.sub(source, target, sqla_source_code)

source = '''(return f"InformationContentEntity\\(creation_date={.*\n+\s+#.*\n\s+__mapper_args__ = )(\{\n.*?\n\s+\})\n'''
target = '''\g<1>{
        'concrete': True,
        'polymorphic_on': type,
        "polymorphic_identity": "InformationContentEntity",
    }'''
if re.search(source, sqla_source_code, re.MULTILINE):
    sqla_source_code = re.sub(source, target, sqla_source_code, re.MULTILINE)

source = '''(return f"<<<SUBHERE>>>\\(.*\n+\s+#.*\n\s+__mapper_args__ = )(\{\n.*?\n\s+\})\n'''
target = '''\g<1>{
        'concrete': True,
        "polymorphic_identity": "<<<SUBHERE>>>",
    }'''
classes_to_edit = ['Note', 
                   'Author', 
                   'Organization', 
                   'ScientificKnowledgeCollection', 
                   'ScientificKnowledgeExpression', 
                   'ScientificKnowledgeFragment',
                   'ScientificKnowledgeItem']
for c in classes_to_edit:
    s = source.replace('<<<SUBHERE>>>', c)
    t = target.replace('<<<SUBHERE>>>', c)
    if re.search(s, sqla_source_code, re.MULTILINE):
        sqla_source_code = re.sub(s, t, sqla_source_code, re.MULTILINE)

source = '''has_notes = relationship\( "Note", secondary="<<<SUBHERE>>>_has_notes"\)\n'''
target = '''has_notes = relationship( "Note", secondary="<<<SUBHERE>>>_has_notes", back_populates="is_about")\n'''
classes_to_edit = ['InformationContentEntity',
                   'Note', 
                   'Author', 
                   'Organization', 
                   'ScientificKnowledgeCollection', 
                   'ScientificKnowledgeExpression', 
                   'ScientificKnowledgeFragment',
                   'ScientificKnowledgeItem']
for c in classes_to_edit:
    s = source.replace('<<<SUBHERE>>>', c)
    t = target.replace('<<<SUBHERE>>>', c)
    if re.search(s, sqla_source_code, re.MULTILINE):
        sqla_source_code = re.sub(s, t, sqla_source_code, re.MULTILINE)

source = '''is_about = relationship\( "InformationContentEntity", secondary="Note_is_about"\)'''
target = '''is_about = relationship( "InformationContentEntity", secondary="Note_is_about", back_populates="has_notes")'''
if re.search(source, sqla_source_code, re.MULTILINE):
    sqla_source_code = re.sub(source, target, sqla_source_code, re.MULTILINE)

os.rename(files(linkml).joinpath('schema_sqla.py'), files(linkml).joinpath('schema_sqla_original.py'))
files(linkml).joinpath('schema_sqla.py').write_text(sqla_source_code)

import difflib

# Delete all foreign keys
raw_sql_source_code = files(linkml).joinpath('schema.sql').read_text()
lines = [l for l in raw_sql_source_code.splitlines() if 'FOREIGN' not in l]
lines = [re.sub('\),\s*$', ')', l) if 'PRIMARY' in l else l for l in lines ]
raw_sql_source_code = '\n'.join(lines)

print(raw_sql_source_code)


os.rename(files(linkml).joinpath('schema.sql'), files(linkml).joinpath('schema_original.sql'))
files(linkml).joinpath('schema.sql').write_text(raw_sql_source_code)

