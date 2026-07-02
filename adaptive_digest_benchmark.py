#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from context_governor import ContextGovernor
EXAMPLES_PATH=Path('examples/messy_contexts.jsonl')
RECEIPTS_PATH=Path('receipts.jsonl')
def load_examples(path:Path)->list[dict]:
    with path.open('r',encoding='utf-8') as f: return [json.loads(line) for line in f if line.strip()]
def yes(v:bool)->str: return 'yes' if v else 'no'
def main()->int:
    RECEIPTS_PATH.write_text('',encoding='utf-8')
    examples=load_examples(EXAMPLES_PATH); gov=ContextGovernor(receipt_log=RECEIPTS_PATH,digest_word_limit=70)
    rows=[]; counts={'green':0,'amber':0,'red':0}; tin=tdig=0
    for item in examples:
        digest,receipt=gov.process(item['latest_message'],item.get('conversation_context',''),active_project=item.get('active_project'),user_preferences=item.get('user_preferences',[]),high_stakes=item.get('high_stakes',False),uploaded_files=item.get('uploaded_files',False),tool_required=item.get('tool_required',False))
        counts[receipt.result]+=1; tin+=receipt.tokens_input_est; tdig+=receipt.tokens_digest_est
        rows.append({'id':item['id'],'expected':item.get('expected_result'),'result':receipt.result,'reason':receipt.pullback_reason or '-','task':yes(receipt.preserved_task),'constraint':yes(receipt.preserved_constraint),'preference':yes(receipt.preserved_preference),'input_words':receipt.tokens_input_est,'digest_words':receipt.tokens_digest_est})
    headers=['id','expected','result','reason','task','constraint','preference','input_words','digest_words']
    widths={h:max(len(h),*(len(str(r[h])) for r in rows)) for h in headers}
    print('OpenLine Context Governor v0.1 benchmark')
    print('='*52)
    print(' | '.join(h.ljust(widths[h]) for h in headers)); print('-'*(sum(widths.values())+3*(len(headers)-1)))
    for r in rows: print(' | '.join(str(r[h]).ljust(widths[h]) for h in headers))
    print('\nSummary'); print('-'*52)
    print(f"examples: {len(rows)}"); print(f"green: {counts['green']} | amber: {counts['amber']} | red: {counts['red']}")
    print(f"input words: {tin}"); print(f"digest words: {tdig}"); print(f"words avoided by digest handoff estimate: {tin-tdig}")
    mismatches=[r for r in rows if r['expected']!=r['result']]
    if mismatches:
        print('\nMismatches')
        for r in mismatches: print(f"- {r['id']}: expected {r['expected']}, got {r['result']} ({r['reason']})")
        return 1
    print('\nAll expected v0.1 classifications matched.'); print('Receipts written to receipts.jsonl'); return 0
if __name__=='__main__': raise SystemExit(main())
