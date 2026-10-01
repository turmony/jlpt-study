"""Apply the user's explicit two-question Hagoromo exception without changing repo policy."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path('.claude/skills/quiz-generate/scripts').resolve()))
import quiz_pipeline as pipeline
original=pipeline.source_errors
def source_errors(source,root,prefix):
    if isinstance(source,dict) and source.get('site_name')=='はごろも':
        if source.get('url')!='https://www.hagoromo-text.work/lookup?vid=1112':
            return [prefix+': Hagoromo exception restricted to vid=1112']
        errors=original(source,root,prefix)
        policy_errors={prefix+'.source.site_name 必须是已核实的日本教学网站',prefix+'.source.url 必须属于已允许的日本教学网站'}
        return [error for error in errors if error not in policy_errors]
    return original(source,root,prefix)
pipeline.source_errors=source_errors
raise SystemExit(pipeline.main())
