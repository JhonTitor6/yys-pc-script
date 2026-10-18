// 只打包页面实际依赖；生产图片仅生成 ID 白名单，不复制到前端。
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const gui = path.join(root, 'gui');
const output = path.join(gui, 'build', 'tauri-frontend');
// 源文件 → staging 路径。裁剪器在 staging 里必须避开 node_modules，
// 否则 Tauri 会以“前端目录包含 node_modules”为由拒绝打包。
const files = [
  ['index.html', 'index.html'],
  ['renderer.js', 'renderer.js'],
  ['styles.css', 'styles.css'],
  ['desktop-bridge.js', 'desktop-bridge.js'],
  ['icon.ico', 'icon.ico'],
  ['node_modules/cropperjs/dist/cropper.min.js', 'cropper.min.js']
];
const CROPPER_SOURCE = './node_modules/cropperjs/dist/cropper.min.js';
const CROPPER_STAGED = './cropper.min.js';
function writeChanged(target, content) {
  for (let current = target; current !== root; current = path.dirname(current)) {
    if (fs.existsSync(current) && fs.lstatSync(current).isSymbolicLink()) throw new Error(`不允许 staging 链接：${current}`);
  }
  fs.mkdirSync(path.dirname(target), { recursive: true });
  if (!fs.existsSync(target) || !fs.readFileSync(target).equals(content)) fs.writeFileSync(target, content);
}
if (fs.existsSync(output)) verify(output);
for (const [source, name] of files) {
  let content = fs.readFileSync(path.join(gui, source));
  if (source === 'index.html') {
    const text = content.toString('utf8');
    if (!text.includes(CROPPER_SOURCE)) throw new Error('index.html 缺少裁剪器引用');
    content = Buffer.from(text.replace(CROPPER_SOURCE, CROPPER_STAGED));
  }
  writeChanged(path.join(output, name), content);
}
// 与 win_util.image.production_image_ids 的生产资源契约一致。
const excluded = new Set(['test', 'tests', 'debug', 'logs', 'example', 'recordings']);
const ids = [];
function scan(directory) {
  for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
    if (item.isSymbolicLink()) throw new Error(`不允许资源链接：${item.name}`);
    const full = path.join(directory, item.name);
    if (item.isDirectory() && !excluded.has(item.name.toLowerCase())) scan(full);
    else if (item.isFile() && /\.(bmp|png)$/i.test(item.name)) ids.push(path.relative(root, full).split(path.sep).join('/'));
  }
}
scan(path.join(root, 'yys'));
writeChanged(path.join(gui, 'build', 'tauri-image-resources.json'), Buffer.from(JSON.stringify(ids.sort())));
function verify(directory) {
  for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, item.name);
    if (item.isSymbolicLink()) throw new Error('staging 不允许符号链接');
    if (item.isDirectory()) verify(full);
    else if (!files.some(([, name]) => name === path.relative(output, full).split(path.sep).join('/'))) throw new Error(`staging 存在非白名单文件：${full}`);
  }
}
verify(output);
console.log(`Tauri staging：${files.length} 个静态文件，${ids.length} 个图片资源 ID`);
