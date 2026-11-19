const $ = s => document.querySelector(s);
const input = $('textarea'), form = $('form'), log = $('#log');
const history = [];
function show(role, content) {
  const item = document.createElement('div'), label = document.createElement('span');
  item.className = `message ${role}`;
  label.className = 'label'; label.textContent = role === 'user' ? 'YOU' : 'FRESHY';
  item.append(label, document.createTextNode(content)); log.append(item);
  item.scrollIntoView({ block: 'end' });
  return item;
}
$('#reset').onclick = () => {
  history.length = 0; log.replaceChildren(); $('#welcome').hidden = false;
  input.value = ''; $('#status').textContent = ''; input.focus();
};
document.querySelectorAll('.ideas button').forEach(b => b.onclick = () => { input.value = b.textContent; input.focus(); });
input.onkeydown = e => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
};
form.onsubmit = async e => {
  e.preventDefault(); const content = input.value.trim(); if (!content || input.disabled) return;
  const turn = { role: 'user', content };
  $('#welcome').hidden = true; const pending = show('user', content);
  input.value = ''; input.disabled = $('#send').disabled = $('#reset').disabled = true;
  $('#status').textContent = 'Freshy is thinking…';
  try {
    const res = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: [...history.slice(-20), turn] }) });
    const data = await res.json(); if (!res.ok) throw new Error(data.error);
    history.push(turn, { role: 'assistant', content: data.reply }); show('assistant', data.reply); $('#status').textContent = '';
  } catch (err) {
    pending.remove(); input.value = content; $('#welcome').hidden = history.length > 0;
    $('#status').textContent = err.message || 'Could not reach Freshy. Please retry.';
  } finally { input.disabled = $('#send').disabled = $('#reset').disabled = false; input.focus(); }
};
