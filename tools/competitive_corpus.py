"""Frozen synthetic developer-memory corpus; no model/provider imports.

Gold stays in the host evaluator, never in the checked-out current repository.
Historical source and observations are the same input artifacts for every profile.
"""
import hashlib
import json
from pathlib import Path
import random

FAMILIES=('numeric_mode_policy','stable_sequence_processing','text_identity_boundaries','sparse_payload_merge')
SCENARIOS=('applicable_history','irrelevant_distractors','withdrawn_policy','changed_interface')
DESCRIPTOR=dict(path='policy.py',symbol='policy')


def definition(family,seed,scenario='applicable_history'):
    rng=random.Random(seed);a,b=rng.sample(range(31,970),2)
    if family==FAMILIES[0]:
        body=f' return {a} if context["flag"] else {b}\n'
        visible=[{'flag':True},{'flag':False}]
        hidden=[{'flag':True,'noise':seed},{'flag':False,'noise':None}]
        extension=-1;broken=' return 0\n'
        policy='Preserve the exact numeric mode policy recorded in the historical source; do not invent new numbers.'
    elif family==FAMILIES[1]:
        body=' result=[]\n for item in context["items"]:\n  if item not in result: result.append(item)\n return result\n'
        visible=[{'items':[3,1,3,2]},{'items':[[2],[1],[2]]}]
        hidden=[{'items':['b','a','b',None,False]},{'items':[{'a':1},{'b':2},{'a':1}]}]
        extension=[];broken=' return sorted(set(context["items"]))\n'
        policy='Stable first-occurrence deduplication by Python equality, including unhashable JSON elements; preserve encounter order.'
    elif family==FAMILIES[2]:
        body=' return context["text"].strip(" ")\n'
        visible=[{'text':' AbC '},{'text':'\tÉx\t'}]
        hidden=[{'text':'  Aß\t  '},{'text':'\u00a0Hello\u00a0'}]
        extension='';broken=' return context["text"].strip().lower()\n'
        policy='Strip only ASCII spaces at both edges, preserving case and every other character, including tabs and non-breaking spaces.'
    else:
        body=' result=context["base"].copy()\n for key,value in context["patch"].items():\n  if value is not None: result[key]=value\n return result\n'
        visible=[{'base':{'a':3,'b':4},'patch':{'a':None,'b':0,'c':False}},{'base':{},'patch':{'empty':'','none':None}}]
        hidden=[{'base':{'keep':seed,'replace':1},'patch':{'keep':None,'replace':False,'zero':0}},{'base':{'x':8},'patch':{'x':'','y':[]}}]
        extension={};broken=' return {key:value for key,value in context["patch"].items() if value}\n'
        policy='Copy the base and overwrite only non-None patch values, preserving false, zero, empty strings and empty collections.'
    old='def policy(context):\n'+body
    namespace={};exec(compile(old,'<frozen-reference>','exec'),namespace)
    expected=lambda values:[dict(value=namespace['policy'](value)) for value in values]
    source='def policy(context):\n if context.get("emergency"): return '+repr(extension)+'\n'+broken
    task='Repair policy.py::policy for compatibility with the applicable historical contract while preserving the new emergency=True extension. Do not guess absent numeric rules. Return no candidate if the historical contract is withdrawn or the interface is incompatible.'
    if scenario=='changed_interface':source=source.replace('policy(context)','policy(context, revision)')
    current_args=repr({'emergency':True})+(', 2' if scenario=='changed_interface' else '')
    test='import unittest\nfrom policy import policy\nclass Policy(unittest.TestCase):\n def test_extension(self):\n  self.assertEqual(policy('+current_args+'),'+repr(extension)+')\n'
    artifact=dict(source_id=f'{family}-{seed}-history',callable=DESCRIPTOR,policy=policy,source=old,
                  observations=[dict(call=dict(args=[value],kwargs={}),expected=value_expected) for value,value_expected in zip(visible,expected(visible))],
                  lifecycle='withdrawn' if scenario=='withdrawn_policy' else 'active',scope='The original one-argument policy(context) interface only.')
    historical_test='import unittest\nfrom policy import policy\nclass Policy(unittest.TestCase):\n def test_history(self):\n'+''.join('  self.assertEqual(policy('+repr(value)+'),'+repr(result['value'])+')\n' for value,result in zip(visible,expected(visible)))
    hidden_calls=[dict(args=[v],kwargs={}) for v in hidden]+[dict(args=[dict(emergency=True)],kwargs={})]
    return dict(id=f'{family}-{seed}-{scenario}',family=family,seed=seed,scenario=scenario,task=task,
                historical_source=old,historical_test=historical_test,current_source=source,current_test=test,artifact=artifact,
                hidden_calls=hidden_calls,hidden_expected=expected(hidden)+[dict(value=extension)],
                expected_action='abstain' if scenario in ('withdrawn_policy','changed_interface') else 'patch')


def corpus():
    development=[definition(family,1701+i) for i,family in enumerate(FAMILIES)]
    reserved=[definition(family,2901+i,SCENARIOS[i]) for i,family in enumerate(FAMILIES)]
    return dict(protocol='synopsis.competitive-corpus.v1',development=development,reserved=reserved,
                limits='Eight synthetic tasks, not real OSS issues; small reserved set cannot establish universal superiority.')


def write_repository(root,item,historical=False):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);tests=root/'tests';tests.mkdir(exist_ok=True)
    (tests/'__init__.py').write_text('')
    (root/'policy.py').write_text(item['historical_source' if historical else 'current_source'])
    (tests/'test_policy.py').write_text(item['historical_test' if historical else 'current_test'])
    # Current lifecycle is visible equally to all profiles. It contains no gold.
    (root/'contract.json').write_text(json.dumps(dict(state=item['artifact']['lifecycle'],interface='revised' if item['scenario']=='changed_interface' else 'policy(context)')))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    raw=json.dumps(corpus(),sort_keys=True,ensure_ascii=False,indent=2)+'\n';args.output.write_text(raw)
    print(hashlib.sha256(raw.encode()).hexdigest())
