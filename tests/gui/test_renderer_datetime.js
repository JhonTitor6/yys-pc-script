const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const filename = path.resolve(__dirname, '../../gui/renderer.js');
const source = fs.readFileSync(filename, 'utf8');
const start = source.indexOf('function parseRecordedTimestamp');
const end = source.indexOf('function formatConfigValue', start);
assert.ok(start >= 0 && end > start);
const { formatDateTime, formatDuration } = vm.runInNewContext(
  `${source.slice(start, end)}\n({ formatDateTime, formatDuration });`, {}, { filename }
);

test('工作台记录按系统时区显示，并按实际经过的时间计算耗时', () => {
  // 产品契约：兼容已有 SQLite UTC 记录和带时区的日志、截图时间。
  const previousTimezone = process.env.TZ;
  try {
    process.env.TZ = 'Asia/Shanghai';
    assert.equal(formatDateTime('2026-11-15 08:58:01'), '2026-11-15 16:58:01');
    assert.equal(formatDateTime('2026-11-15T08:58:01.123Z'), '2026-11-15 16:58:01');
    assert.equal(formatDateTime('2026-11-15T16:58:01+08:00'), '2026-11-15 16:58:01');
    assert.equal(formatDateTime('2026-11-15 23:58:01'), '2026-11-16 07:58:01');
    assert.equal(formatDateTime(null), '—');
    assert.equal(formatDateTime('无效时间'), '—');

    process.env.TZ = 'America/Los_Angeles';
    assert.equal(formatDateTime('2026-03-08 09:59:59'), '2026-03-08 01:59:59');
    assert.equal(formatDateTime('2026-03-08T10:00:01Z'), '2026-03-08 03:00:01');
    assert.equal(formatDuration('2026-03-08 09:59:59', '2026-03-08T03:00:01-07:00'), '0分02秒');
  } finally {
    if (previousTimezone === undefined) delete process.env.TZ;
    else process.env.TZ = previousTimezone;
  }
});
