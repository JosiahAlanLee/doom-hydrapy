// SPDX-License-Identifier: GPL-2.0-or-later
// Optional CPU/WebGL parity check. Requires Playwright and importable HydraPy.
const { spawnSync } = require('child_process');
const path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const width = 640, height = 400;

const fixture = spawnSync(process.env.PYTHON || 'python3', ['-c', `
import base64, json, numpy as np
from hydrapy.backend_np import Env
from rogue.optics import GLSL, numpy_optics
encode = lambda a: base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()
env = Env(640, 400, filter='nearest')
source = np.random.default_rng(29).integers(0, 256, (400, 640, 4), dtype=np.uint8)
tex = source.astype(np.float32) / 255
cases = []
for tic, raw in [(0,1), (35,1), (0,0), (1,0), (5,0), (27,0), (28,0), (35,0),
                 ('NaN',0), (35,'NaN'), (-1,0), (36,0)]:
    out = numpy_optics(tex, env.base_st, tic, raw, env)
    cases.append(dict(tic=tic, raw=raw, expected=encode(np.rint(out*255).astype(np.uint8))))
print(json.dumps(dict(glsl=GLSL, source=encode(source), cases=cases)))
`], { cwd: root, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
if (fixture.status !== 0) throw Error(fixture.stderr || 'Could not create NumPy fixtures');
const data = JSON.parse(fixture.stdout);

async function main() {
  const browser = await chromium.launch({
    ...(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {}),
    args: ['--no-sandbox', '--enable-unsafe-swiftshader'],
  });
  try {
    const page = await browser.newPage();
    const result = await page.evaluate(({ payload, width, height }) => {
      const canvas = document.createElement('canvas');
      canvas.width = width; canvas.height = height;
      const gl = canvas.getContext('webgl', {
        alpha: true, antialias: false, premultipliedAlpha: false, preserveDrawingBuffer: true,
      });
      if (!gl) throw Error('WebGL unavailable');
      function compile(type, source) {
        const shader = gl.createShader(type);
        gl.shaderSource(shader, source); gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
          throw Error(gl.getShaderInfoLog(shader));
        }
        return shader;
      }
      const vertex = 'attribute vec2 position;void main(){gl_Position=vec4(position,0.,1.);}';
      const fragment = `precision highp float;
        uniform sampler2D inputFrame;
        uniform vec2 resolution;
        uniform float warning, rawMode;
        vec4 optics(sampler2D _tex, vec2 _st, float surveyor_tic, float raw) {
          ${payload.glsl}
        }
        void main() {
          gl_FragColor=optics(inputFrame,gl_FragCoord.xy/resolution,warning,rawMode);
        }`;
      const program = gl.createProgram();
      gl.attachShader(program, compile(gl.VERTEX_SHADER, vertex));
      gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragment));
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        throw Error(gl.getProgramInfoLog(program));
      }
      gl.useProgram(program);
      const buffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
      const location = gl.getAttribLocation(program, 'position');
      gl.enableVertexAttribArray(location);
      gl.vertexAttribPointer(location, 2, gl.FLOAT, false, 0, 0);

      const decode = value => Uint8Array.from(atob(value), c => c.charCodeAt(0));
      const source = decode(payload.source);
      gl.activeTexture(gl.TEXTURE0);
      const texture = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, source);
      gl.uniform1i(gl.getUniformLocation(program, 'inputFrame'), 0);
      gl.uniform2f(gl.getUniformLocation(program, 'resolution'), width, height);
      gl.disable(gl.DITHER);
      gl.viewport(0, 0, width, height);
      const warningLocation = gl.getUniformLocation(program, 'warning');
      const rawLocation = gl.getUniformLocation(program, 'rawMode');

      const checks = [];
      for (const entry of payload.cases) {
        const tic = Number(entry.tic), raw = Number(entry.raw);
        gl.uniform1f(warningLocation, tic); gl.uniform1f(rawLocation, raw);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
        const pixels = new Uint8Array(source.length);
        gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
        if (gl.getError() !== gl.NO_ERROR) throw Error('WebGL error');
        const expected = decode(entry.expected);
        const bypass = !(raw >= 0 && raw < .5) || !(tic >= 0 && tic <= 35);
        let maxError = 0, protectedChanges = 0;
        for (let i = 0; i < pixels.length; i++) {
          maxError = Math.max(maxError, Math.abs(pixels[i] - expected[i]));
          const pixel = Math.floor(i / 4), x = pixel % width;
          const y = height - 1 - Math.floor(pixel / width);
          const protectedPixel = y < 88 || y >= 353 || (x >= 308 && x < 333 && y >= 180 && y < 209);
          if ((bypass || protectedPixel) && pixels[i] !== source[i]) protectedChanges++;
        }
        const check = { tic: entry.tic, raw: entry.raw, max_error: maxError, protected_changes: protectedChanges };
        checks.push(check);
        if (maxError > 2 || protectedChanges) throw Error('Pixel parity failed ' + JSON.stringify(check));
      }
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      const renderer = gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER);
      return { renderer, checks };
    }, { payload: data, width, height });
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
