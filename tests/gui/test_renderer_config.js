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

testSelectValuesUseSchemaTypes();
testStringSelectValuesRemainStrings();
testExistingNumberAndBooleanConversionsRemainUnchanged();
console.log('renderer config normalization tests passed');
