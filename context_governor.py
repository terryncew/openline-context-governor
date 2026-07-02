#!/usr/bin/env python3
"""
OpenLine Context Governor v0.1

A tiny, dependency-free context handoff governor.
"""
from __future__ import annotations
import argparse, hashlib, json, re, time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

NEGATION_PATTERNS=[r"\bwithout\b[^.?!;,\n]*",r"\bdo not\b[^.?!;,\n]*",r"\bdon't\b[^.?!;,\n]*",r"\bnever\b[^.?!;,\n]*",r"\bno\b\s+\w+[^.?!;,\n]*",r"\bavoid\b[^.?!;,\n]*",r"\bunless\b[^.?!;,\n]*",r"\bexcept\b[^.?!;,\n]*"]
CONSTRAINT_PATTERNS=[r"\bmust\b[^.?!;,\n]*",r"\bkeep\b[^.?!;,\n]*",r"\bunder\b\s+\d+[^.?!;,\n]*",r"\bwithin\b[^.?!;,\n]*",r"\bonly\b[^.?!;,\n]*",r"\buse\b[^.?!;,\n]*",r"\bdo not\b[^.?!;,\n]*",r"\bwithout\b[^.?!;,\n]*"]
PREFERENCE_PATTERNS=[r"\bprefer\b[^.?!;,\n]*",r"\bI like\b[^.?!;,\n]*",r"\bI want\b[^.?!;,\n]*",r"\bmy style\b[^.?!;,\n]*",r"\bremember\b[^.?!;,\n]*"]
RISK_WORDS={"medical":"high_stakes_context","legal":"high_stakes_context","tax":"high_stakes_context","financial":"high_stakes_context","lawsuit":"high_stakes_context","uploaded":"uploaded_file_needed","attached":"uploaded_file_needed","pdf":"uploaded_file_needed","spreadsheet":"uploaded_file_needed","run":"tool_required","test":"tool_required","verify":"tool_required","search":"tool_required"}

def _sha256_text(text:str)->str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
def _words(text:str)->list[str]:
    return re.findall(r"\S+", text.strip())
def _shorten(text:str, limit:int)->str:
    words=_words(text)
    return text.strip() if len(words)<=limit else " ".join(words[:limit]).strip()
def _find_patterns(text:str, patterns:Iterable[str])->list[str]:
    found=[]
    seen=set()
    for pattern in patterns:
        for match in re.findall(pattern,text,flags=re.IGNORECASE):
            cleaned=" ".join(match.split()).strip()
            key=cleaned.lower()
            if cleaned and key not in seen:
                found.append(cleaned); seen.add(key)
    return found
def _sentence_head(text:str)->str:
    chunks=re.split(r"(?<=[.?!])\s+", text.strip())
    return next((c.strip() for c in chunks if c.strip()), _shorten(text,24))
def _risk_flags(text:str, high_stakes=False, uploaded_files=False, tool_required=False)->list[str]:
    flags=set(); lowered=text.lower()
    for word,flag in RISK_WORDS.items():
        if word in lowered: flags.add(flag)
    if high_stakes: flags.add('high_stakes_context')
    if uploaded_files: flags.add('uploaded_file_needed')
    if tool_required: flags.add('tool_required')
    return sorted(flags)

@dataclass(frozen=True)
class Digest:
    task:str
    user_intent:str
    active_project:str|None
    must_preserve:list[str]
    open_claims:list[str]
    risk_flags:list[str]
    pullback_conditions:list[str]
    digest_text:str
    truncated:bool
    truncated_fields:list[str]=field(default_factory=list)
    def canonical_json(self)->str:
        return json.dumps(asdict(self),sort_keys=True,separators=(',',':'))

@dataclass(frozen=True)
class Receipt:
    claim:str
    action:str
    evidence_hash:str
    digest_hash:str
    full_context_hash:str
    timestamp:int
    witness:str
    result:str
    preserved_task:bool
    preserved_claim:bool
    preserved_constraint:bool
    preserved_preference:bool
    risk_flag:list[str]
    pullback_reason:str|None
    tokens_input_est:int
    tokens_digest_est:int
    next_use_note:str
    def canonical_json(self)->str:
        return json.dumps(asdict(self),sort_keys=True,separators=(',',':'))

class ContextGovernor:
    def __init__(self, receipt_log:str|Path='receipts.jsonl', digest_word_limit:int=80)->None:
        self.receipt_log=Path(receipt_log); self.digest_word_limit=digest_word_limit
    def process(self, latest_message:str, conversation_context:str='', *, active_project:str|None=None, user_preferences:list[str]|None=None, high_stakes=False, uploaded_files=False, tool_required=False, write_receipt=True)->tuple[Digest,Receipt]:
        full_context=(conversation_context.strip()+"\n\n"+latest_message.strip()).strip()
        digest=self.create_digest(latest_message=latest_message, conversation_context=conversation_context, active_project=active_project, user_preferences=user_preferences or [], high_stakes=high_stakes, uploaded_files=uploaded_files, tool_required=tool_required)
        receipt=self.witness_check(digest=digest, full_context=full_context)
        if write_receipt: self.append_receipt(receipt)
        return digest, receipt
    def create_digest(self, *, latest_message:str, conversation_context:str='', active_project:str|None=None, user_preferences:list[str]|None=None, high_stakes=False, uploaded_files=False, tool_required=False)->Digest:
        full_context=(conversation_context.strip()+"\n\n"+latest_message.strip()).strip()
        task=_sentence_head(latest_message)
        constraints=_find_patterns(full_context,CONSTRAINT_PATTERNS)
        negations=_find_patterns(full_context,NEGATION_PATTERNS)
        preferences=list(user_preferences or [])+_find_patterns(full_context,PREFERENCE_PATTERNS)
        must=[]; seen=set()
        for item in constraints+negations+preferences:
            key=item.lower()
            if key not in seen: must.append(item); seen.add(key)
        open_claims=[]
        if re.search(r"\b(claim|says|argues|evidence|source|because)\b", full_context, re.I): open_claims.append(_shorten(latest_message,30))
        flags=_risk_flags(full_context, high_stakes=high_stakes, uploaded_files=uploaded_files, tool_required=tool_required)
        pullback=sorted(set(flags))
        if negations: pullback.append('negation_lost')
        if not must and len(_words(full_context))>self.digest_word_limit: pullback.append('claim_ambiguous')
        protected=' | '.join(must[:5])
        raw=f"Task: {task}"
        if active_project: raw+=f"\nProject: {active_project}"
        if protected: raw+=f"\nMust preserve: {protected}"
        if open_claims: raw+=f"\nOpen claim: {open_claims[0]}"
        if flags: raw+=f"\nRisk flags: {', '.join(flags)}"
        digest_text=_shorten(raw,self.digest_word_limit)
        truncated=len(_words(raw))>self.digest_word_limit
        return Digest(task,_shorten(latest_message,30),active_project,must,open_claims,flags,pullback,digest_text,truncated,['digest_text'] if truncated else [])
    def witness_check(self, *, digest:Digest, full_context:str)->Receipt:
        digest_blob=digest.canonical_json(); digest_lower=digest_blob.lower()
        preserved_task=bool(digest.task and digest.task.lower() in digest_lower)
        preserved_claim=not digest.open_claims or any(c.lower()[:20] in digest_lower for c in digest.open_claims)
        required_constraints=_find_patterns(full_context,CONSTRAINT_PATTERNS)
        required_preferences=_find_patterns(full_context,PREFERENCE_PATTERNS)
        required_negations=_find_patterns(full_context,NEGATION_PATTERNS)
        preserved_constraint=all(c.lower() in digest_lower for c in required_constraints[:5])
        preserved_preference=all(p.lower() in digest_lower for p in required_preferences[:5])
        negation_preserved=all(n.lower() in digest_lower for n in required_negations[:5])
        result='green'; reason=None
        if not preserved_task: result='amber'; reason='claim_ambiguous'
        if required_constraints and not preserved_constraint: result='amber'; reason='constraint_missing'
        if required_preferences and not preserved_preference: result='amber'; reason='preference_missing'
        if required_negations and not negation_preserved: result='amber'; reason='negation_lost'
        if 'uploaded_file_needed' in digest.risk_flags: result='amber'; reason=reason or 'uploaded_file_needed'
        if 'tool_required' in digest.risk_flags: result='amber'; reason=reason or 'tool_required'
        if 'high_stakes_context' in digest.risk_flags: result='red'; reason='high_stakes_context'
        if result=='green': action='handoff_digest'; claim='digest_preserved'; note='Pass digest to answer agent.'
        else: action='pullback_full_context'; claim='needs_pullback'; note='Request fuller context before answering.'
        return Receipt(claim,action,'sha256:'+_sha256_text(full_context),'sha256:'+_sha256_text(digest_blob),'sha256:'+_sha256_text(full_context),int(time.time()),'openline-context-governor-v0.1',result,preserved_task,preserved_claim,preserved_constraint,preserved_preference,digest.risk_flags,reason,len(_words(full_context)),len(_words(digest.digest_text)),note)
    def append_receipt(self, receipt:Receipt)->None:
        self.receipt_log.parent.mkdir(parents=True,exist_ok=True)
        with self.receipt_log.open('a',encoding='utf-8') as f: f.write(receipt.canonical_json()+"\n")

def main()->int:
    p=argparse.ArgumentParser(description='Run a single context-governor pass.')
    p.add_argument('message'); p.add_argument('--context',default=''); p.add_argument('--project',default=None)
    p.add_argument('--high-stakes',action='store_true'); p.add_argument('--uploaded-files',action='store_true'); p.add_argument('--tool-required',action='store_true')
    a=p.parse_args()
    d,r=ContextGovernor().process(a.message,a.context,active_project=a.project,high_stakes=a.high_stakes,uploaded_files=a.uploaded_files,tool_required=a.tool_required)
    print(json.dumps({'digest':asdict(d),'receipt':asdict(r)},indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
