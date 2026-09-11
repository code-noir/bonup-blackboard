"""Local registry-only CLI. No authority impersonation, agent execution or push."""
import argparse
import json
import sqlite3
import sys

from .registry import Registry
from .serialization import parse_json
from .types import ValidationError


def main(argv=None):
    parser=argparse.ArgumentParser(prog='python -m tools.agent_control')
    parser.add_argument('--state',required=True,help='Explicit external SQLite path; no production default')
    parser.add_argument('--history',help='Separate bare Git history path; required only for init')
    group=parser.add_subparsers(dest='group',required=True)
    registry=group.add_parser('registry').add_subparsers(dest='command',required=True)
    init=registry.add_parser('init');init.add_argument('--operation-id',required=True)
    registry.add_parser('status')
    task=group.add_parser('task').add_subparsers(dest='command',required=True)
    create=task.add_parser('create');create.add_argument('--operation-id',required=True)
    create.add_argument('--input',default='-',help='Sanitized proposal JSON file, or stdin')
    show=task.add_parser('show');show.add_argument('task_id')
    task.add_parser('list')
    finding=group.add_parser('finding').add_subparsers(dest='command',required=True)
    listing=finding.add_parser('list');listing.add_argument('--task-id');listing.add_argument('--unresolved',action='store_true')
    history=group.add_parser('history').add_subparsers(dest='command',required=True);history.add_parser('verify')
    publication=group.add_parser('publication').add_subparsers(dest='command',required=True)
    publication.add_parser('status')
    reconcile=publication.add_parser('reconcile');reconcile.add_argument('--operation-id',required=True)
    args=parser.parse_args(argv)
    try:
        if args.group=='registry' and args.command=='init':
            if not args.history:parser.error('--history is required for initialization')
            with Registry.initialize(args.state,args.history,operation_id=args.operation_id) as db:result=db.verify()
        else:
            with Registry(args.state) as db:
                if args.group=='registry' or args.group=='history':result=db.verify()
                elif args.group=='publication':
                    result=db.publication_status() if args.command=='status' else db.reconcile(operation_id=args.operation_id)
                else:
                    if db.verify()['status']=='BLOCKED':raise ValidationError('Registry is blocked.')
                    if args.group=='task':
                        if args.command=='create':
                            if args.input=='-':proposal=parse_json(sys.stdin.read())
                            else:
                                with open(args.input,encoding='utf-8') as stream:proposal=parse_json(stream.read())
                            result=db.create_task(proposal,operation_id=args.operation_id).to_dict()
                        elif args.command=='show':result=db.get_task(args.task_id).to_dict()
                        else:result=[t.to_dict() for t in db.list_tasks()]
                    else:result=[r.to_dict() for r in db.list_records(args.task_id,args.unresolved)]
        print(json.dumps(result,sort_keys=True,indent=2))
        return 2 if isinstance(result,dict) and result.get('status')=='BLOCKED' else 0
    except (ValidationError,sqlite3.DatabaseError,OSError,KeyError,TypeError):
        print(json.dumps({'status':'BLOCKED','error':'Registry operation rejected; inspect trusted local state.'}),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
