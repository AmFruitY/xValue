"use client";

import Image from "next/image";
import { useEffect, useRef } from "react";
import { emitNeuralSignal, SIGNAL_EVENT, type NeuralSignal } from "./neural-signals";

// Smooth joint weights keep the original texture and adjacent mesh edges continuous.
const vertexSource = `
precision mediump float;
attribute vec2 a_position;
uniform float u_time, u_motion, u_gesture, u_state, u_emphasis, u_focus;
varying vec2 v_uv;
vec2 turn(vec2 p, vec2 pivot, float angle) {
  vec2 q=p-pivot; float c=cos(angle),s=sin(angle);
  return pivot+vec2(q.x*c-q.y*s,q.x*s+q.y*c);
}
float region(vec2 p, vec2 center, vec2 radius) { vec2 q=(p-center)/radius; return exp(-dot(q,q)*2.0); }
void main() {
  vec2 p=a_position*vec2(1024.,1536.), q=p;
  float t=u_time, m=u_motion, gesture=u_gesture*u_emphasis;
  float cycle=mod(t,6.2);
  float control=smoothstep(1.2,1.8,cycle)*(1.-smoothstep(2.,2.7,cycle));
  float ball=smoothstep(805.,855.,p.x)*smoothstep(1075.,1125.,p.y)*(1.-smoothstep(1350.,1430.,p.y));
  float body=1.-ball;
  q.x+=sin(t*1.13)*5.*region(p,vec2(580.,520.),vec2(350.,650.))*body*m;
  q.y-=sin(t*1.63)*5.*region(p,vec2(585.,440.),vec2(320.,360.))*body*m;
  float head=region(p,vec2(704.,214.),vec2(170.,215.));
  q+=(turn(p,vec2(650.,330.),(sin(t*.83)*.028+gesture*u_focus*.05)*m)-p)*head;
  float armL=(1.-smoothstep(450.,525.,p.x))*smoothstep(205.,290.,p.y)*(1.-smoothstep(540.,655.,p.y));
  float indicate=u_state>1.5 ? .11 : .055;
  q+=(turn(p,vec2(465.,310.),(sin(t*1.04+.6)*.035*u_emphasis+gesture*indicate)*m)-p)*armL;
  float armR=smoothstep(715.,795.,p.x)*smoothstep(330.,410.,p.y)*(1.-smoothstep(740.,850.,p.y));
  float greeting=u_state<1.5 ? sin(t*5.)*.12 : -.06;
  q+=(turn(p,vec2(746.,385.),(sin(t*.92+2.)*.038*u_emphasis+gesture*greeting)*m)-p)*armR;
  float backLeg=(1.-smoothstep(545.,620.,p.x))*smoothstep(780.,870.,p.y);
  q+=(turn(p,vec2(520.,790.),sin(t*1.1+1.)*.021*m)-p)*backLeg;
  float foot=region(p,vec2(790.,1210.),vec2(95.,185.))*body;
  q.x-=control*12.*foot*m; q.y-=control*26.*foot*m;
  q.x-=control*24.*ball*m; q.y-=control*70.*ball*m;
  q+=(turn(p,vec2(910.,1220.),control*.21*m)-p)*ball;
  v_uv=a_position;
  gl_Position=vec4(q.x/512.-1.,1.-q.y/768.,0.,1.);
}`;
const fragmentSource = `
precision mediump float;
uniform sampler2D u_texture;
uniform float u_time, u_motion, u_gesture;
varying vec2 v_uv;
void main() {
  vec4 c=texture2D(u_texture,v_uv);
  float phase=mod(u_time*.33,1.6);
  float sweep=exp(-pow((v_uv.y-phase)*21.,2.));
  float weave=.5+.5*sin(v_uv.x*80.+v_uv.y*90.-u_time*2.);
  c.rgb+=vec3(.26,.70,.85)*(sweep*.34+u_gesture*.17+weave*.025)*u_motion;
  gl_FragColor=c;
}`;

export function Footballer({ animated = false, compact = false, visible = true }: { animated?: boolean; compact?: boolean; visible?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const visibilityRef = useRef(visible);
  useEffect(() => { visibilityRef.current = visible; }, [visible]);
  useEffect(() => {
    const canvas = canvasRef.current, root = rootRef.current;
    if (!canvas || !root) return;
    const gl = canvas.getContext("webgl", { alpha: true, premultipliedAlpha: false, antialias: true });
    if (!gl) return;
    const shaders: WebGLShader[] = [];
    const makeShader = (type: number, source: string) => {
      const shader = gl.createShader(type); if (!shader) return null;
      shaders.push(shader); gl.shaderSource(shader, source); gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) { root.dataset.rendererError = gl.getShaderInfoLog(shader) ?? "shader"; return null; }
      return shader;
    };
    const vertex = makeShader(gl.VERTEX_SHADER, vertexSource), fragment = makeShader(gl.FRAGMENT_SHADER, fragmentSource);
    const program = gl.createProgram();
    if (!vertex || !fragment || !program) { shaders.forEach((s) => gl.deleteShader(s)); return; }
    gl.attachShader(program, vertex); gl.attachShader(program, fragment); gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) { root.dataset.rendererError = gl.getProgramInfoLog(program) ?? "program"; shaders.forEach((s) => gl.deleteShader(s)); gl.deleteProgram(program); return; }
    gl.useProgram(program);
    const columns = 26, rows = 39, vertices: number[] = [], indices: number[] = [];
    for (let y = 0; y <= rows; y++) for (let x = 0; x <= columns; x++) vertices.push(x / columns, y / rows);
    for (let y = 0; y < rows; y++) for (let x = 0; x < columns; x++) { const a = y * (columns + 1) + x, b = a + columns + 1; indices.push(a, b, a + 1, a + 1, b, b + 1); }
    const positions = gl.createBuffer(), elements = gl.createBuffer(), texture = gl.createTexture();
    gl.bindBuffer(gl.ARRAY_BUFFER, positions); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(vertices), gl.STATIC_DRAW);
    const location = gl.getAttribLocation(program, "a_position"); gl.enableVertexAttribArray(location); gl.vertexAttribPointer(location, 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, elements); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(indices), gl.STATIC_DRAW);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.uniform1i(gl.getUniformLocation(program, "u_texture"), 0);
    const timeUniform = gl.getUniformLocation(program, "u_time"), motionUniform = gl.getUniformLocation(program, "u_motion"), gestureUniform = gl.getUniformLocation(program, "u_gesture"), stateUniform = gl.getUniformLocation(program, "u_state"), focusUniform = gl.getUniformLocation(program, "u_focus");
    gl.uniform1f(gl.getUniformLocation(program, "u_emphasis"), compact ? 1.5 : 1);
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    let loaded = false, disposed = false, frame = 0, last = 0, time = 0, inView = true, gestureAt = -10000, gestureKind = 0, focus = -1, previousCycle = 0, contactTimer: ReturnType<typeof setTimeout> | undefined;
    const image = new window.Image();
    const resize = () => { const rect = canvas.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 1.5); canvas.width = Math.max(1, Math.round(rect.width * dpr)); canvas.height = Math.max(1, Math.round(rect.height * dpr)); gl.viewport(0, 0, canvas.width, canvas.height); render(); };
    function render() {
      if (!loaded || gl!.isContextLost()) return;
      const age = (performance.now() - gestureAt) / 1000;
      const gesture = age < 3 ? Math.sin(Math.min(1, age / 3) * Math.PI) : 0;
      if (age >= 3) root!.dataset.state = "idle";
      gl!.uniform1f(timeUniform, time); gl!.uniform1f(motionUniform, animated && !preference.matches ? 1 : 0); gl!.uniform1f(gestureUniform, gesture);
      gl!.uniform1f(stateUniform, gestureKind); gl!.uniform1f(focusUniform, focus);
      gl!.clearColor(0, 0, 0, 0); gl!.clear(gl!.COLOR_BUFFER_BIT); gl!.drawElements(gl!.TRIANGLES, indices.length, gl!.UNSIGNED_SHORT, 0);
    }
    const tick = (timestamp: number) => {
      frame = requestAnimationFrame(tick);
      if (document.hidden || !inView || !visibilityRef.current || preference.matches || !animated) { last = timestamp; return; }
      if (timestamp - last < 32) return;
      time += Math.min((timestamp - (last || timestamp)) / 1000, .08); last = timestamp;
      const cycle = time % 6.2;
      if (!compact && previousCycle < 2.7 && cycle >= 2.7) {
        const rect = root.getBoundingClientRect();
        emitNeuralSignal("kick", [], { x: rect.left + rect.width * .87, y: rect.top + rect.height * .80 });
        root.dataset.contact = "true"; clearTimeout(contactTimer); contactTimer = setTimeout(() => { delete root.dataset.contact; }, 1000);
      }
      previousCycle = cycle; render();
    };
    const receive = (event: Event) => {
      const signal = (event as CustomEvent<NeuralSignal>).detail; if (signal.kind === "kick") return;
      gestureAt = performance.now(); gestureKind = signal.kind === "welcome" ? 1 : signal.kind === "select" ? 2 : 3;
      const target = signal.routes[0] && document.querySelector(`[data-neural="${signal.routes[0].to}"]`), targetRect = target?.getBoundingClientRect(), actorRect = root.getBoundingClientRect();
      focus = targetRect && targetRect.left + targetRect.width / 2 > actorRect.left + actorRect.width / 2 ? 1 : -1;
      root.dataset.state = gestureKind === 1 ? "welcome" : gestureKind === 2 ? "attention" : "explain"; render();
    };
    const motionChanged = () => render();
    const observer = new ResizeObserver(resize); observer.observe(canvas);
    const intersection = new IntersectionObserver(([entry]) => { inView = entry.isIntersecting; }, { rootMargin: "40px" }); intersection.observe(canvas);
    const contextLost = (event: Event) => { event.preventDefault(); root.classList.remove("footballer-ready"); };
    canvas.addEventListener("webglcontextlost", contextLost);
    window.addEventListener(SIGNAL_EVENT, receive); preference.addEventListener("change", motionChanged);
    image.onload = () => { if (disposed) return; gl.bindTexture(gl.TEXTURE_2D, texture); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image); loaded = true; resize(); root.classList.add("footballer-ready"); };
    image.src = "/images/xvalue-footballer.png";
    frame = requestAnimationFrame(tick);
    return () => { disposed = true; clearTimeout(contactTimer); cancelAnimationFrame(frame); observer.disconnect(); intersection.disconnect(); preference.removeEventListener("change", motionChanged); window.removeEventListener(SIGNAL_EVENT, receive); canvas.removeEventListener("webglcontextlost", contextLost); image.onload = null; root.classList.remove("footballer-ready"); gl.deleteBuffer(positions); gl.deleteBuffer(elements); gl.deleteTexture(texture); shaders.forEach((s) => gl.deleteShader(s)); gl.deleteProgram(program); };
  }, [animated, compact]);
  return <div ref={rootRef} data-state="idle" className={`footballer footballer-mesh ${animated ? "footballer-animated" : ""} ${compact ? "footballer-compact" : ""}`} aria-hidden="true">
    <Image className="footballer-fallback" src="/images/xvalue-footballer.png" alt="" width={1024} height={1536} priority sizes={compact ? "100px" : "(max-width: 700px) 80vw, 560px"} />
    <canvas ref={canvasRef} className="footballer-skin" />
    {!compact && <><span className="footballer-floor" /><span className="footballer-contact" /><svg className="footballer-paths" viewBox="0 0 500 700" fill="none"><path className="footballer-fiber" d="M95 205C355 115 485 240 235 350S45 485 395 548" /><path className="footballer-fiber" d="M88 245C205 135 420 182 415 355S145 497 390 581" /><path className="footballer-pulse" d="M95 205C355 115 485 240 235 350S45 485 395 548" /></svg></>}
  </div>;
}
