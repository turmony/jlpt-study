"""Validate the explicitly authorized two-question source exception only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path('.claude/skills/quiz-generate/scripts').resolve()))
import quiz_pipeline as pipeline
original=pipeline.source_errors
def source_errors(source,root,prefix):
 if isinstance(source,dict) and source.get('site_name')=='毎日のんびり日本語教師':
  if source.get('url')!='https://mainichi-nonbiri.com/grammar/n2-younara/':return [prefix+': exception restricted to authorized n2-younara page']
  policy_errors={prefix+'.source.site_name 必须是已核实的日本教学网站',prefix+'.source.url 必须属于已允许的日本教学网站'}
  return [e for e in original(source,root,prefix) if e not in policy_errors]
 return original(source,root,prefix)
pipeline.source_errors=source_errors
raise SystemExit(pipeline.main())
