const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function loadNormalizeConfigValue() {
  const filename = path.resolve(__dirname, '../../gui/renderer.js');
  const source = fs.readFileSync(filename, 'utf8');
  const start = source.indexOf('function normalizeConfigValue');
  const end = source.indexOf('\nasync function startScript', start);
  assert.ok(start >= 0, '找不到 normalizeConfigValue');
  assert.ok(end > start, '找不到 normalizeConfigValue 的结束位置');

  const context = {};
  vm.runInNewContext(
    `${source.slice(start, end)}\nthis.normalizeConfigValue = normalizeConfigValue;`,
    context,
    { filename }
  );
  return context.normalizeConfigValue;
}

function testSelectValuesUseSchemaTypes() {
  // 产品契约：下拉框提交值必须恢复为 config_schema.options 定义的原始类型。
  const normalizeConfigValue = loadNormalizeConfigValue();
  const selectField = {
    field_type: 'select',
    options: [
      { value: 0, label: '拒绝' },
      { value: 1, label: '全部接受' },
      { value: 2, label: '只接勾协' }
    ]
  };

  assert.strictEqual(normalizeConfigValue('0', selectField), 0);
  assert.strictEqual(normalizeConfigValue('2', selectField), 2);
  assert.strictEqual(normalizeConfigValue('3', selectField), '3');
}

function testStringSelectValuesRemainStrings() {
  const normalizeConfigValue = loadNormalizeConfigValue();
  const selectField = {
    field_type: 'select',
    options: [
      { value: 'manual', label: '手动' },
      { value: 'scheduled', label: '定时' }
    ]
  };

  assert.strictEqual(normalizeConfigValue('scheduled', selectField), 'scheduled');
}

function testExistingNumberAndBooleanConversionsRemainUnchanged() {
  const normalizeConfigValue = loadNormalizeConfigValue();

  assert.strictEqual(
    normalizeConfigValue('103', { field_type: 'number' }),
    103
  );
  assert.strictEqual(
    normalizeConfigValue('true', { field_type: 'boolean' }),
    true
  );
}

function testImageResourceSettingsContract() {
  // 产品契约：图片管理留在设置页，目录打开通过 Electron IPC，其余操作使用图片资源 API。
  const renderer = fs.readFileSync(path.resolve(__dirname, '../../gui/renderer.js'), 'utf8');
  const html = fs.readFileSync(path.resolve(__dirname, '../../gui/index.html'), 'utf8');
  assert.ok(html.includes('id="imageResourceSearch"'));
  assert.ok(html.includes('id="imageResourceList"'));
  assert.ok(html.includes('<details id="imageResourcesSection"'));
  assert.ok(html.includes('class="settings-section-summary"'));
  assert.ok(html.includes('accept=".bmp,.png,image/bmp,image/png"'));
  assert.ok(html.includes('<dialog id="imageResourceConfirmDialog"'));
  assert.ok(html.includes('aria-describedby="imageResourceConfirmMessage"'));
  assert.ok(html.includes('<form method="dialog">'));
  assert.ok(html.includes('id="imageResourceConfirmPreview"'));
  assert.ok(html.includes('id="imageResourceConfirmPath"'));
  assert.ok(html.includes('id="imagePreviewDialog"'));
  assert.ok(html.includes('id="imagePreviewImage"'));
  assert.ok(html.includes('id="imageResourceConfirmCancel" class="button quiet" type="submit" value="cancel"'));
  assert.ok(renderer.includes("apiGet('/api/image-resources')"));
  assert.ok(renderer.includes('/api/image-resources/content?'));
  assert.ok(renderer.includes('/api/image-resources/override?resource_id='));
  assert.ok(renderer.includes('data-image-preview-resource'));
  assert.ok(renderer.includes('data-image-open-directory'));
  assert.ok(renderer.includes('openImagePreview'));
  assert.ok(renderer.includes('openImageResourceDirectory'));
  assert.ok(renderer.includes('item.filename.toLowerCase().includes(query)'));
  assert.ok(renderer.includes('item.resource_id.toLowerCase().includes(query)'));
  const start = renderer.indexOf('async function replaceImageResource');
  const end = renderer.indexOf('\nfunction setNavCollapsed', start);
  const resourceActions = renderer.slice(start, end);
  assert.ok(renderer.includes("dialog.returnValue = 'cancel'"));
  assert.ok(renderer.includes("dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm')"));
  assert.ok(resourceActions.includes('confirmImageResourceAction'));
  assert.ok(resourceActions.includes('if (!confirmed) return;'));
  assert.ok(resourceActions.indexOf('if (!confirmed) return;') < resourceActions.indexOf('apiPutBinary'));
  assert.ok(resourceActions.lastIndexOf('if (!confirmed) return;') < resourceActions.indexOf('apiDelete'));
  assert.ok(!resourceActions.includes('window.confirm'));
  assert.ok(!resourceActions.includes('/api/runs'));
}

function testScreenshotCropperContract() {
  // 产品契约：截图独立于运行动作，本地固定 Cropper.js v2 按选择区输出 PNG。
  const renderer = fs.readFileSync(path.resolve(__dirname, '../../gui/renderer.js'), 'utf8');
  const html = fs.readFileSync(path.resolve(__dirname, '../../gui/index.html'), 'utf8');
  const preload = fs.readFileSync(path.resolve(__dirname, '../../gui/preload.js'), 'utf8');
  const main = fs.readFileSync(path.resolve(__dirname, '../../gui/main.js'), 'utf8');
  const packageJson = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../gui/package.json'), 'utf8'));

  assert.strictEqual(packageJson.dependencies.cropperjs, '2.1.1');
  assert.ok(packageJson.build.files.includes('node_modules/cropperjs/dist/cropper.min.js'));
  assert.ok(html.includes('id="captureScreenshotButton"'));
  assert.ok(html.includes('id="screenshotCropDialog"'));
  assert.ok(html.includes('id="screenshotLibrary"'));
  assert.ok(html.includes('<script src="./node_modules/cropperjs/dist/cropper.min.js"></script>'));
  assert.ok(!html.match(/https?:\/\/[^"']*cropper/i));
  assert.ok(renderer.includes("apiPost('/api/screenshots/capture')"));
  assert.ok(renderer.includes("apiGet('/api/screenshots')"));
  assert.ok(renderer.includes('data-image-preview-screenshot'));
  assert.ok(renderer.includes('.getCropperSelection?.()'));
  assert.ok(renderer.includes('await selection.$toCanvas({ width, height })'));
  assert.ok(renderer.includes('selection.width <= 0 || selection.height <= 0'));
  assert.ok(renderer.indexOf('selection.width <= 0 || selection.height <= 0') < renderer.indexOf('await selection.$toCanvas({ width, height })'));
  assert.ok(renderer.includes('selectionRect.width * source.width / imageRect.width'));
  assert.ok(renderer.includes('selectionRect.right > imageRect.right + epsilon'));
  assert.ok(renderer.includes('cropperImage.rotatable = false'));
  assert.ok(renderer.includes('restoreRequired = saved.restore_required === true'));
  assert.ok(renderer.includes('restoreRequired = error.restoreRequired === true'));
  assert.ok(!renderer.includes('const shouldRestoreGui = !state.currentRun'));
  assert.ok(renderer.includes("item.available === false"));
  assert.ok(renderer.includes('截图文件已删除或不可用。'));
  assert.ok(renderer.includes('/api/image-resources/override?resource_id='));
  assert.ok(renderer.includes('confirmImageResourceAction'));
  assert.ok(preload.includes("ipcRenderer.invoke('restore-gui-focus')"));
  assert.ok(preload.includes("ipcRenderer.invoke('open-image-resource-directory'"));
  assert.ok(main.includes("ipcMain.handle('restore-gui-focus'"));
  assert.ok(main.includes("ipcMain.handle('open-image-resource-directory'"));
}

testSelectValuesUseSchemaTypes();
testStringSelectValuesRemainStrings();
testExistingNumberAndBooleanConversionsRemainUnchanged();
testImageResourceSettingsContract();
testScreenshotCropperContract();
console.log('renderer config normalization tests passed');
