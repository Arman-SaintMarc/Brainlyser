/* Browser regression test. Requires Playwright + its Chromium installation.
 * Run: node scripts/validate_dashboard.cjs [processed-output-directory]
 */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const app = path.resolve(__dirname, '../Code/Brainlyser code');
const requested = process.argv[2] && path.resolve(process.argv[2]);
const lastPath = requested ? '../' + path.relative(app, requested).split(path.sep).join('/') :
    JSON.parse(fs.readFileSync(path.join(app, 'interface/js/last_path.js'), 'utf8').match(/=\s*(".*")/)[1]);
const output = requested || path.resolve(app, 'interface', lastPath);
const data = JSON.parse(fs.readFileSync(path.join(output, 'brain_slice_data.json'), 'utf8'));
const brains = Object.fromEntries(data.flatMap(entry => Object.entries(entry).map(([name, rows]) => [name, rows[0]])));
const expectedSlices = Object.values(brains).reduce((n, brain) => n + Object.keys(brain.images).length, 0);
const contentTypes = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.jpg':'image/jpeg', '.png':'image/png'};
const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    if (pathname.endsWith('/js/last_path.js')) {
        res.setHeader('Content-Type', 'text/javascript'); res.end(`const lastPath = ${JSON.stringify(lastPath)};`); return;
    }
    const file = path.resolve(app, '.' + pathname);
    if (!file.startsWith(app + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
        res.writeHead(404); res.end('Not found'); return;
    }
    res.setHeader('Content-Type', contentTypes[path.extname(file)] || 'application/octet-stream');
    fs.createReadStream(file).pipe(res);
});

(async () => {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const browser = await chromium.launch({headless: true});
    try {
        const context = await browser.newContext({viewport:{width:1440,height:1000}});
        const base = `http://127.0.0.1:${server.address().port}`;
        await context.route('**/*', route => route.request().url().startsWith(base) ? route.continue() : route.abort());
        for (const file of ['index.html','brain.html','comparaison.html','difference.html']) {
            const page = await context.newPage();
            const errors = [];
            page.on('pageerror', err => errors.push(err.message));
            page.on('response', res => { if (res.status() >= 400 && !res.url().endsWith('favicon.ico')) errors.push(`${res.status()} ${res.url()}`); });
            await page.goto(`${base}/interface/${file}`);
            if (file === 'index.html') {
                await page.waitForFunction(() => document.getElementById('totalBrains').textContent !== '--');
                assert.equal(await page.locator('#totalBrains').innerText(), String(Object.keys(brains).length));
                assert.equal(await page.locator('#totalSlices').innerText(), String(expectedSlices));
                assert.deepEqual(await page.evaluate(() => [xGrid[0], xGrid.at(-1)]), [1,220]);
                await page.locator('#smoothToggle').check();
                await page.locator('#smoothToggle').uncheck();
            } else {
                const select = file === 'comparaison.html' ? '#classSelect1' : '#classSelectDiff1';
                await page.waitForFunction(selector => document.querySelector(selector).options.length > 1, select);
                const firstBrain = Object.keys(brains)[0];
                const firstClass = brains[firstBrain].class;
                const levels = Object.values(brains[firstBrain].images).map(slice => Number(slice.atlas.match(/\d+/)[0]));
                const setLevel = async level => page.locator('#sliceSlider').evaluate((el, value) => { el.value=value; el.dispatchEvent(new Event('input')); }, level);
                await setLevel(levels[Math.floor(levels.length/2)]);
                if (file === 'brain.html') await page.selectOption(select, firstBrain);
                else if (file === 'comparaison.html') await page.selectOption(select, firstClass);
                else {
                    const classes = [...new Set(Object.values(brains).map(brain => brain.class))];
                    if (classes.length > 1) {
                        await page.selectOption('#classSelectDiff1', classes[0]);
                        await page.selectOption('#classSelectDiff2', classes[1]);
                        const levelsFor = cls => new Set(Object.values(brains).filter(brain => brain.class === cls)
                            .flatMap(brain => Object.values(brain.images).map(slice => slice.atlas)));
                        const common = [...levelsFor(classes[0])].filter(level => levelsFor(classes[1]).has(level));
                        if (common.length) {
                            await setLevel(Number(common[Math.floor(common.length/2)].match(/\d+/)[0]));
                            await page.waitForFunction(() => document.getElementById('differenceImage').naturalWidth > 0 &&
                                document.getElementById('differenceImage').style.display === 'block');
                            await page.waitForFunction(() => document.getElementById('differenceOutline').naturalWidth > 0 &&
                                document.getElementById('differenceOutline').style.display === 'block');
                        }
                    }
                }
                await page.waitForTimeout(350);
                const broken = await page.locator('img').evaluateAll(elements => elements.filter(el =>
                    el.getAttribute('src') && el.complete && !el.naturalWidth && getComputedStyle(el).display !== 'none').map(el => el.src));
                assert.deepEqual(broken, []);
                for (const level of [1,220]) { await setLevel(level); await page.waitForTimeout(250); }
            }
            assert.deepEqual(errors, [], `${file}: browser errors`);
            console.log(`PASS ${file}`);
            await page.close();
        }
        // Real dashboard code with known synthetic endpoint values. Fixtures
        // are supplied only to this test page, never written to experimental data.
        const endpointPage = await context.newPage();
        const endpointData = [
            {control:[{class:'CT-F',images:{a:{atlas:'slice0001.jpg',brainRegion1:{median:5}},b:{atlas:'slice0220.jpg',brainRegion1:{median:10}}}}]},
            {disease:[{class:'AD-F',images:{a:{atlas:'slice0001.jpg',brainRegion1:{median:8}},b:{atlas:'slice0220.jpg',brainRegion1:{median:17}}}}]}
        ];
        await endpointPage.route('**/brain_slice_data.js', route => route.fulfill({contentType:'text/javascript',body:`const imageData = ${JSON.stringify(endpointData)};`}));
        await endpointPage.goto(`${base}/interface/index.html`);
        await endpointPage.waitForFunction(() => document.getElementById('plotlyHeatmapF').data?.length);
        const endpoints = await endpointPage.evaluate(() => {
            const trace = document.getElementById('plotlyHeatmapF').data[0];
            return [trace.x[0], trace.x.at(-1), trace.z[0][0], trace.z[0].at(-1)];
        });
        assert.deepEqual(endpoints, [1,220,3,7]);
        console.log('PASS dashboard numerical endpoints 1 and 220');
        await endpointPage.close();
        console.log(JSON.stringify({brains:Object.keys(brains).length, slices:expectedSlices, output}));
    } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exitCode=1; });
