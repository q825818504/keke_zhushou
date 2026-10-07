// Build a closed set of user-facing functions, without shipping the editor.
const fs = require('node:fs');
const path = require('node:path');
const acorn = require('acorn');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
const ast = acorn.parse(source, { ecmaVersion: 'latest' });
const declarations = new Map();
for (const node of ast.body) {
  if (node.type === 'FunctionDeclaration') declarations.set(node.id.name, node);
  if (node.type === 'VariableDeclaration') {
    for (const declaration of node.declarations) {
      if (declaration.id.type !== 'Identifier') throw Error('Unsupported top-level binding');
      declarations.set(declaration.id.name, node);
    }
  }
}
const replacements = new Map([
  ['applyCharacter', 'function applyCharacter(name, options = {}) { const data = characterData[name]; if (!data) return; selectedCharacter = name; activeKnowledge = data.knowledge; if (options.skipUserRail) { renderUserHero(activeKnowledge); renderUserTabPanel(activeKnowledge); } else renderUserExperience(activeKnowledge); }'],
  ['showUserExperience', 'function showUserExperience() { document.body.classList.add("user-mode"); renderUserRouteView("team"); }'],
]);
const binder = declarations.get('bindUserExperience');
replacements.set('bindUserExperience', source.slice(binder.start, binder.end).replace(/^.*userAdminButton.*$/m, ''));
function textOf(node) {
  return (replacements.get(node.id?.name) || source.slice(node.start, node.end))
    .replaceAll('当前浏览器', '这台电脑').replaceAll('用户端 · ', '');
}
function identifiers(code) {
  const found = new Set();
  function visit(node, parent, key) {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'Identifier') {
      if (parent?.type === 'MemberExpression' && key === 'property' && !parent.computed) return;
      if (parent?.type === 'Property' && key === 'key' && !parent.computed && !parent.shorthand) return;
      found.add(node.name);
    }
    for (const [field, value] of Object.entries(node)) {
      if (Array.isArray(value)) value.forEach(child => visit(child, node, field));
      else if (value && typeof value === 'object') visit(value, node, field);
    }
  }
  visit(acorn.parse(code, { ecmaVersion: 'latest' }));
  return found;
}
const selected = new Set();
const queue = ['bindUserExperience', 'showUserExperience', 'applyCharacter'];
while (queue.length) {
  const node = declarations.get(queue.pop());
  if (!node || selected.has(node)) continue;
  selected.add(node);
  for (const name of identifiers(textOf(node))) if (declarations.has(name)) queue.push(name);
}
const output = ast.body.filter(node => selected.has(node)).map(textOf).join('\n\n')
  + '\nconst desktopInitialCharacter = Object.entries(characterData).find(([,data]) => data.id === "zhenhong")?.[0] || Object.keys(characterData)[0];\napplyCharacter(desktopInitialCharacter, { silent: true });\nbindUserExperience();\nshowUserExperience();\n';
for (const forbidden of ['KekeAdminBridge', 'showRoleManagement', 'bindSave', 'persistCharacter', 'guideCanLeave', 'putDriveLayoutRecord', 'deleteDriveLayoutRecord']) {
  if (output.includes(forbidden)) throw Error('User build contains admin dependency: ' + forbidden);
}
acorn.parse(output, { ecmaVersion: 'latest' });
fs.writeFileSync(process.argv[2], output);
console.log('User-only JavaScript: ' + selected.size + ' declarations; admin functions excluded.');
