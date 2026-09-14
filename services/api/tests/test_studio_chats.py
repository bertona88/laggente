from sqlalchemy import select
from app import database
from app.models import Account, Conversation, Space


def test_studio_chats_preserve_history_and_space(professional_client, app):
    client = professional_client
    original = client.get('/api/v1/studio/messages').json()['conversation']['id']
    before = client.get('/api/v1/studio/space').json()
    fresh = client.post('/api/v1/studio/chats').json()['id']
    assert fresh != original
    reply = client.post(f'/api/v1/studio/messages?conversation_id={fresh}', json={'content': 'Organizziamo i documenti'})
    assert reply.status_code == 200, reply.text
    assert app.state.assistant_service.studio_calls[-1]['messages'][-1].conversation_id == fresh
    new_messages = client.get(f'/api/v1/studio/messages?conversation_id={fresh}').json()['messages']
    old_messages = client.get(f'/api/v1/studio/messages?conversation_id={original}').json()['messages']
    assert any(m['content'] == 'Organizziamo i documenti' for m in new_messages)
    assert all(m['content'] != 'Organizziamo i documenti' for m in old_messages)
    assert client.get('/api/v1/studio/messages').json()['conversation']['id'] == original
    assert client.get('/api/v1/studio/space').json() == before
    page = client.get('/api/v1/studio/chats?limit=1').json()
    assert page['items'][0]['id'] == fresh
    assert page['items'][0]['title'] == 'Organizziamo i documenti'
    assert page['has_more']
    assert client.get('/api/v1/studio/chats?limit=1&offset=1').json()['items'][0]['id'] == original


def test_studio_chat_selection_enforces_tenant_and_kind(professional_client):
    with database.SessionLocal() as db:
        space = db.scalar(select(Space))
        other = Account(name='Other'); db.add(other); db.flush()
        foreign = Conversation(account_id=other.id, space_id=space.id, kind='studio', title='Private')
        public = Conversation(account_id=space.account_id, space_id=space.id, kind='public')
        db.add_all([foreign, public]); db.commit()
        ids = [foreign.id, public.id]
    for chat in ids:
        assert professional_client.get(f'/api/v1/studio/messages?conversation_id={chat}').status_code == 404
        assert professional_client.post(f'/api/v1/studio/messages?conversation_id={chat}', json={'content':'Hello'}).status_code == 404
    items = professional_client.get('/api/v1/studio/chats').json()['items']
    assert not any(item['id'] in ids for item in items)


def test_new_chat_requires_authentication(client):
    assert client.post('/api/v1/studio/chats').status_code == 401
    assert client.get('/api/v1/studio/chats').status_code == 401
