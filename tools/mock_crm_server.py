import asyncio
import json
import sys
import time
import uuid
from typing import Any
TICKET_DB: dict[str, dict] = {}
STATUSES = ['open', 'in_progress', 'pending', 'resolved', 'closed']
PRIORITIES = ['low', 'medium', 'high', 'urgent']
TICKET_TYPES = ['Bug', 'Question', 'Feature Request', 'Billing', 'Account']

def _new_ticket(subject: str, description: str, priority: str, ticket_type: str, source: str) -> dict:
    tid = f'CRM-{str(uuid.uuid4())[:8].upper()}'
    ticket = {'id': tid, 'subject': subject, 'description': description, 'priority': priority if priority in PRIORITIES else 'medium', 'type': ticket_type if ticket_type in TICKET_TYPES else 'Question', 'status': 'open', 'source': source, 'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'notes': [], 'assignee': None}
    TICKET_DB[tid] = ticket
    return ticket

def handle_crm_create_ticket(args: dict) -> dict:
    ticket = _new_ticket(subject=args.get('subject', 'Untitled'), description=args.get('description', ''), priority=args.get('priority', 'medium'), ticket_type=args.get('type', 'Question'), source=args.get('source', 'api'))
    return {'success': True, 'ticket_id': ticket['id'], 'message': f"Ticket {ticket['id']} created with status 'open'.", 'ticket': ticket}

def handle_crm_get_ticket(args: dict) -> dict:
    tid = args.get('ticket_id', '')
    if tid not in TICKET_DB:
        return {'success': False, 'error': f'Ticket {tid} not found.'}
    return {'success': True, 'ticket': TICKET_DB[tid]}

def handle_crm_update_ticket(args: dict) -> dict:
    tid = args.get('ticket_id', '')
    if tid not in TICKET_DB:
        return {'success': False, 'error': f'Ticket {tid} not found.'}
    ticket = TICKET_DB[tid]
    if 'status' in args and args['status'] in STATUSES:
        ticket['status'] = args['status']
    if 'priority' in args and args['priority'] in PRIORITIES:
        ticket['priority'] = args['priority']
    if 'assignee' in args:
        ticket['assignee'] = args['assignee']
    ticket['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    return {'success': True, 'message': f'Ticket {tid} updated.', 'ticket': ticket}

def handle_crm_add_note(args: dict) -> dict:
    tid = args.get('ticket_id', '')
    if tid not in TICKET_DB:
        return {'success': False, 'error': f'Ticket {tid} not found.'}
    note = {'id': str(uuid.uuid4())[:8], 'body': args.get('body', ''), 'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'private': args.get('private', True)}
    TICKET_DB[tid]['notes'].append(note)
    TICKET_DB[tid]['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    return {'success': True, 'message': f'Note added to {tid}.', 'note': note}

def handle_crm_resolve_ticket(args: dict) -> dict:
    tid = args.get('ticket_id', '')
    if tid not in TICKET_DB:
        return {'success': False, 'error': f'Ticket {tid} not found.'}
    TICKET_DB[tid]['status'] = 'resolved'
    TICKET_DB[tid]['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    return {'success': True, 'message': f'Ticket {tid} has been resolved.', 'ticket': TICKET_DB[tid]}

def handle_crm_list_tickets(args: dict) -> dict:
    status_filter = args.get('status', None)
    limit = int(args.get('limit', 10))
    tickets = list(TICKET_DB.values())
    if status_filter:
        tickets = [t for t in tickets if t['status'] == status_filter]
    return {'success': True, 'count': len(tickets[:limit]), 'tickets': tickets[:limit]}

def handle_crm_search_tickets(args: dict) -> dict:
    query = args.get('query', '').lower()
    results = [t for t in TICKET_DB.values() if query in t['subject'].lower() or query in t['description'].lower()]
    return {'success': True, 'count': len(results), 'tickets': results[:10]}
TOOL_HANDLERS = {'crm_create_ticket': handle_crm_create_ticket, 'crm_get_ticket': handle_crm_get_ticket, 'crm_update_ticket': handle_crm_update_ticket, 'crm_add_note': handle_crm_add_note, 'crm_resolve_ticket': handle_crm_resolve_ticket, 'crm_list_tickets': handle_crm_list_tickets, 'crm_search_tickets': handle_crm_search_tickets}
TOOL_SCHEMAS = [{'name': 'crm_create_ticket', 'description': 'Create a new CRM support ticket (Linear mock).', 'inputSchema': {'type': 'object', 'properties': {'subject': {'type': 'string', 'description': 'Ticket subject/title'}, 'description': {'type': 'string', 'description': 'Ticket description'}, 'priority': {'type': 'string', 'enum': PRIORITIES, 'default': 'medium'}, 'type': {'type': 'string', 'enum': TICKET_TYPES, 'default': 'Question'}, 'source': {'type': 'string', 'default': 'api'}}, 'required': ['subject', 'description']}}, {'name': 'crm_get_ticket', 'description': 'Get CRM ticket details by ticket ID.', 'inputSchema': {'type': 'object', 'properties': {'ticket_id': {'type': 'string'}}, 'required': ['ticket_id']}}, {'name': 'crm_update_ticket', 'description': "Update a CRM ticket's status, priority, or assignee.", 'inputSchema': {'type': 'object', 'properties': {'ticket_id': {'type': 'string'}, 'status': {'type': 'string', 'enum': STATUSES}, 'priority': {'type': 'string', 'enum': PRIORITIES}, 'assignee': {'type': 'string'}}, 'required': ['ticket_id']}}, {'name': 'crm_add_note', 'description': 'Add an internal note to a CRM ticket.', 'inputSchema': {'type': 'object', 'properties': {'ticket_id': {'type': 'string'}, 'body': {'type': 'string'}, 'private': {'type': 'boolean', 'default': True}}, 'required': ['ticket_id', 'body']}}, {'name': 'crm_resolve_ticket', 'description': 'Mark a CRM ticket as resolved.', 'inputSchema': {'type': 'object', 'properties': {'ticket_id': {'type': 'string'}}, 'required': ['ticket_id']}}, {'name': 'crm_list_tickets', 'description': 'List recent CRM tickets with optional status filter.', 'inputSchema': {'type': 'object', 'properties': {'status': {'type': 'string', 'enum': STATUSES}, 'limit': {'type': 'integer', 'default': 10}}}}, {'name': 'crm_search_tickets', 'description': 'Search CRM tickets by keyword in subject or description.', 'inputSchema': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']}}]

def build_response(request_id: Any, result: Any) -> dict:
    return {'jsonrpc': '2.0', 'id': request_id, 'result': result}

def build_error(request_id: Any, code: int, message: str) -> dict:
    return {'jsonrpc': '2.0', 'id': request_id, 'error': {'code': code, 'message': message}}

async def handle_request(request: dict) -> dict:
    method = request.get('method', '')
    params = request.get('params', {})
    req_id = request.get('id')
    if method == 'initialize':
        return build_response(req_id, {'protocolVersion': '2024-11-05', 'serverInfo': {'name': 'mock-crm-server', 'version': '1.0.0'}, 'capabilities': {'tools': {}}})
    elif method == 'notifications/initialized':
        return None
    elif method == 'tools/list':
        return build_response(req_id, {'tools': TOOL_SCHEMAS})
    elif method == 'tools/call':
        tool_name = params.get('name', '')
        arguments = params.get('arguments', {})
        if tool_name not in TOOL_HANDLERS:
            return build_error(req_id, -32601, f'Unknown tool: {tool_name}')
        try:
            result = TOOL_HANDLERS[tool_name](arguments)
            return build_response(req_id, {'content': [{'type': 'text', 'text': json.dumps(result, indent=2)}], 'isError': False})
        except Exception as e:
            return build_response(req_id, {'content': [{'type': 'text', 'text': json.dumps({'error': str(e)})}], 'isError': True})
    else:
        return build_error(req_id, -32601, f'Method not found: {method}')

async def main():
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)
    writer_transport, writer_protocol = await loop.connect_write_pipe(asyncio.BaseProtocol, sys.stdout.buffer)
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, loop)
    while True:
        try:
            line = await reader.readline()
            if not line:
                break
            request = json.loads(line.decode('utf-8').strip())
            response = await handle_request(request)
            if response is not None:
                out = json.dumps(response) + '\n'
                writer.write(out.encode('utf-8'))
                await writer.drain()
        except json.JSONDecodeError as e:
            err = build_error(None, -32700, f'Parse error: {e}')
            writer.write((json.dumps(err) + '\n').encode('utf-8'))
            await writer.drain()
        except Exception as e:
            sys.stderr.write(f'[mock-crm-server] Error: {e}\n')
            sys.stderr.flush()
if __name__ == '__main__':
    asyncio.run(main())
