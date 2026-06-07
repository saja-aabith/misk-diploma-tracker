import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';

/**
 * SkillsConstellation — the student "My Profile" view: the MSHPL dimensions
 * as a slowly drifting star field on a nebula. ACP shows all 20 HPL leaf
 * characteristics (each inheriting its group's score); VAA shows its 11. Reads
 * the SAME computed profile as the radars (GET /student/skills-profile); does
 * no maths of its own.
 *
 * Mapping (feel, not precision — the radars are the precise view):
 *   - distance from centre, star size, and glow all scale with the 0–100 score
 *   - ACP ("How I Think") stars are warm gold, VAA ("Who I Am") stars aqua-teal
 *   - dimensions with no evidence yet sit faint near the centre, muted label
 *
 * Honours prefers-reduced-motion: renders a single static frame (no spin/twinkle).
 * Cleans up the renderer, animation frame and GPU resources on unmount so
 * switching tabs never leaks a WebGL context.
 *
 * Props: profile (skills-profile payload), studentName (string).
 */
function SkillsConstellation({ profile, studentName }) {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !profile || !Array.isArray(profile.dimensions)) return undefined;

    const HEIGHT = 460;
    let width = mount.clientWidth || 600;
    const reduced =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x020308, 0.014);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, HEIGHT);
    renderer.setClearColor(0x020308, 1);
    mount.appendChild(renderer.domElement);

    const camera = new THREE.PerspectiveCamera(45, width / HEIGHT, 0.1, 200);
    camera.position.set(0, 2.6, 13.5);
    camera.lookAt(0, 0.3, 0);

    scene.add(new THREE.AmbientLight(0x4a7c69, 0.6));
    const pl = new THREE.PointLight(0xeafff7, 1.7);
    pl.position.set(5, 8, 9);
    scene.add(pl);
    const rim = new THREE.PointLight(0x9b8cff, 0.45);
    rim.position.set(-7, -3, 4);
    scene.add(rim);

    const disposables = [];
    const track = (obj) => {
      disposables.push(obj);
      return obj;
    };

    const glowCanvas = document.createElement('canvas');
    glowCanvas.width = 128;
    glowCanvas.height = 128;
    const gctx = glowCanvas.getContext('2d');
    const grad = gctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    grad.addColorStop(0, 'rgba(255,255,255,1)');
    grad.addColorStop(0.22, 'rgba(255,255,255,0.75)');
    grad.addColorStop(0.5, 'rgba(255,255,255,0.2)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    gctx.fillStyle = grad;
    gctx.fillRect(0, 0, 128, 128);
    const GLOW = track(new THREE.CanvasTexture(glowCanvas));

    const nebCanvas = document.createElement('canvas');
    nebCanvas.width = 1024;
    nebCanvas.height = 1024;
    const nctx = nebCanvas.getContext('2d');
    nctx.fillStyle = '#020308';
    nctx.fillRect(0, 0, 1024, 1024);
    nctx.globalCompositeOperation = 'lighter';
    const blobs = [['#142a5e', 460], ['#0e4d5e', 380], ['#2e1a55', 360], ['#0b3d2f', 320], ['#0d2350', 400], ['#491a44', 240]];
    for (let b = 0; b < 12; b++) {
      const spec = blobs[b % blobs.length];
      const rad = spec[1] * (0.45 + Math.random() * 0.8);
      const cxp = Math.random() * 1024;
      const cyp = Math.random() * 1024;
      const g2 = nctx.createRadialGradient(cxp, cyp, 0, cxp, cyp, rad);
      g2.addColorStop(0, spec[0]);
      g2.addColorStop(1, 'rgba(0,0,0,0)');
      nctx.globalAlpha = 0.06;
      nctx.fillStyle = g2;
      nctx.beginPath();
      nctx.arc(cxp, cyp, rad, 0, Math.PI * 2);
      nctx.fill();
    }
    nctx.globalAlpha = 1;
    nctx.globalCompositeOperation = 'source-over';
    for (let s = 0; s < 1600; s++) {
      const sr = Math.random();
      const tint = sr > 0.92 ? '184,202,255' : sr > 0.85 ? '255,224,188' : '238,250,247';
      nctx.fillStyle = 'rgba(' + tint + ',' + (Math.random() * 0.85 + 0.12) + ')';
      nctx.beginPath();
      nctx.arc(Math.random() * 1024, Math.random() * 1024, Math.random() * 1.5 + 0.3, 0, Math.PI * 2);
      nctx.fill();
    }
    const nebTex = track(new THREE.CanvasTexture(nebCanvas));
    const skyGeo = track(new THREE.SphereGeometry(60, 40, 40));
    const skyMat = track(new THREE.MeshBasicMaterial({ map: nebTex, side: THREE.BackSide, fog: false }));
    const sky = new THREE.Mesh(skyGeo, skyMat);
    scene.add(sky);

    const depthN = 700;
    const depthArr = new Float32Array(depthN * 3);
    for (let i = 0; i < depthN; i++) {
      const rr = 18 + Math.random() * 30;
      const th = Math.random() * Math.PI * 2;
      const ph = Math.acos(2 * Math.random() - 1);
      depthArr[i * 3] = rr * Math.sin(ph) * Math.cos(th);
      depthArr[i * 3 + 1] = rr * Math.cos(ph);
      depthArr[i * 3 + 2] = rr * Math.sin(ph) * Math.sin(th);
    }
    const depthGeo = track(new THREE.BufferGeometry());
    depthGeo.setAttribute('position', new THREE.BufferAttribute(depthArr, 3));
    const depthMat = track(new THREE.PointsMaterial({ map: GLOW, color: 0xbff3e2, size: 0.5, transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending, depthWrite: false }));
    const depth = new THREE.Points(depthGeo, depthMat);
    scene.add(depth);

    const makeLabel = (text, w, muted) => {
      const c = document.createElement('canvas');
      c.width = 360;
      c.height = 60;
      const x = c.getContext('2d');
      x.font = '22px sans-serif';
      x.fillStyle = 'rgba(5,19,15,0.5)';
      const bw = Math.min(346, x.measureText(text).width + 28);
      const bx = (360 - bw) / 2;
      if (x.roundRect) {
        x.beginPath();
        x.roundRect(bx, 12, bw, 36, 10);
        x.fill();
      } else {
        x.fillRect(bx, 12, bw, 36);
      }
      x.fillStyle = muted ? 'rgba(170,190,182,0.9)' : 'rgba(236,251,246,0.98)';
      x.textAlign = 'center';
      x.textBaseline = 'middle';
      x.fillText(text, 180, 31);
      const tex = track(new THREE.CanvasTexture(c));
      tex.minFilter = THREE.LinearFilter;
      const mat = track(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, depthTest: false }));
      const sp = new THREE.Sprite(mat);
      sp.scale.set(w, w * 0.166, 1);
      return sp;
    };

    // A bigger, bolder plate for the student's own name at the hub.
    const makeNameLabel = (text) => {
      const c = document.createElement('canvas');
      c.width = 512;
      c.height = 110;
      const x = c.getContext('2d');
      x.font = 'bold 36px sans-serif';
      const bw = Math.min(496, x.measureText(text).width + 64);
      const bx = (512 - bw) / 2;
      x.fillStyle = 'rgba(2,102,75,0.94)';
      if (x.roundRect) {
        x.beginPath();
        x.roundRect(bx, 28, bw, 56, 18);
        x.fill();
        x.lineWidth = 2.5;
        x.strokeStyle = 'rgba(61,240,189,0.85)';
        x.stroke();
      } else {
        x.fillRect(bx, 28, bw, 56);
      }
      x.fillStyle = 'rgba(255,255,255,0.99)';
      x.textAlign = 'center';
      x.textBaseline = 'middle';
      x.fillText(text, 256, 57);
      const tex = track(new THREE.CanvasTexture(c));
      tex.minFilter = THREE.LinearFilter;
      const mat = track(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, depthTest: false }));
      const sp = new THREE.Sprite(mat);
      sp.scale.set(4.2, 0.9, 1);
      return sp;
    };

    // Procedural green "world" surface for the student hub — base gradient,
    // darker continents, faint highlights. Keeps the MISK green palette.
    const makePlanetTexture = () => {
      const c = document.createElement('canvas');
      c.width = 256;
      c.height = 256;
      const x = c.getContext('2d');
      const base = x.createLinearGradient(0, 0, 0, 256);
      base.addColorStop(0, '#16d79a');
      base.addColorStop(1, '#0a8f66');
      x.fillStyle = base;
      x.fillRect(0, 0, 256, 256);
      for (let i = 0; i < 26; i++) {
        const cxp = Math.random() * 256;
        const cyp = Math.random() * 256;
        const rr = 14 + Math.random() * 42;
        const g = x.createRadialGradient(cxp, cyp, 0, cxp, cyp, rr);
        g.addColorStop(0, Math.random() > 0.5 ? 'rgba(3,77,55,0.55)' : 'rgba(6,107,75,0.5)');
        g.addColorStop(1, 'rgba(0,0,0,0)');
        x.fillStyle = g;
        x.beginPath();
        x.arc(cxp, cyp, rr, 0, Math.PI * 2);
        x.fill();
      }
      for (let i = 0; i < 40; i++) {
        x.fillStyle = 'rgba(190,255,230,' + (Math.random() * 0.22 + 0.05) + ')';
        x.beginPath();
        x.arc(Math.random() * 256, Math.random() * 256, Math.random() * 2 + 0.5, 0, Math.PI * 2);
        x.fill();
      }
      return track(new THREE.CanvasTexture(c));
    };

    const root = new THREE.Group();
    scene.add(root);
    const acp = Array.isArray(profile.acp_leaves)
      ? profile.acp_leaves
      : profile.dimensions.filter((d) => d.group === 'ACP');
    const vaa = profile.dimensions.filter((d) => d.group === 'VAA');
    const twinkle = [];
    const nodePos = {};

    // Two orbit groups, each spun on its own axis in the animation loop:
    // acpGroup ("How I Think", gold) rides a VERTICAL ring (spun around Z);
    // vaaGroup ("Who I Am", violet) rides a HORIZONTAL ring (spun around Y).
    const acpGroup = new THREE.Group();
    const vaaGroup = new THREE.Group();
    root.add(acpGroup);
    root.add(vaaGroup);

    const placeGroup = (list, isACP) => {
      const group = isACP ? acpGroup : vaaGroup;
      const gc = list.length || 1;
      list.forEach((d, ig) => {
        const ang = (ig / gc) * Math.PI * 2 + (isACP ? 0.2 : 0.3);
        const v = Math.max(0, Math.min(100, Number(d.score) || 0));
        const empty = d.status === 'no_evidence' || v === 0;
        // ACP sits in the XY plane (vertical ring, slightly tighter so the top
        // and bottom stay on-screen); VAA sits in the XZ plane (horizontal ring).
        let pos;
        if (isACP) {
          const r = empty ? 2.0 : 2.4 + (v / 100) * 2.6;
          pos = new THREE.Vector3(Math.cos(ang) * r, Math.sin(ang) * r, Math.sin(ig * 1.7) * 0.35);
        } else {
          const r = empty ? 2.2 : 2.9 + (v / 100) * 3.4;
          pos = new THREE.Vector3(Math.cos(ang) * r, Math.sin(ig * 1.7) * 0.35, Math.sin(ang) * r);
        }
        nodePos[d.dimension] = pos;

        const col = empty ? 0x6f8f86 : isACP ? 0xffc861 : 0xb06bff;
        const surfaceCol = empty ? 0x90a8a0 : isACP ? 0xffe2a6 : 0xe7d4ff;
        const coreSize = empty ? 0.10 : 0.16 + (v / 100) * 0.20;
        const coreGeo = track(new THREE.SphereGeometry(coreSize, 28, 28));
        const coreMat = track(new THREE.MeshStandardMaterial({
          color: surfaceCol,
          emissive: col,
          emissiveIntensity: empty ? 0.25 : 0.6,
          roughness: 0.45,
          metalness: 0.1,
        }));
        const coreMesh = new THREE.Mesh(coreGeo, coreMat);
        coreMesh.position.copy(pos);
        group.add(coreMesh);

        const gsz = empty ? 0.4 : 0.8 + (v / 100) * 1.5;
        const glowMat = track(new THREE.SpriteMaterial({ map: GLOW, color: col, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, opacity: empty ? 0.28 : 0.95 }));
        const glow = new THREE.Sprite(glowMat);
        glow.scale.set(gsz, gsz, 1);
        glow.position.copy(pos);
        group.add(glow);
        if (!empty) twinkle.push({ sp: glow, base: gsz, ph: Math.random() * 6.28 });

        const labelText = empty ? d.dimension : d.dimension + '  ' + v;
        const lab = makeLabel(labelText, 2.7, empty);
        lab.position.copy(pos.clone().add(new THREE.Vector3(0, coreSize + 0.42, 0)));
        group.add(lab);

        const lineGeo = track(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), pos]));
        const lineMat = track(new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: empty ? 0.06 : 0.13 }));
        group.add(new THREE.Line(lineGeo, lineMat));
      });
    };
    placeGroup(acp, true);
    placeGroup(vaa, false);

    const loop = (list, color, group) => {
      const pts = list.map((d) => nodePos[d.dimension]).filter(Boolean);
      if (pts.length < 3) return;
      const curve = new THREE.CatmullRomCurve3(pts, true, 'catmullrom', 0.4);
      const geo = track(new THREE.BufferGeometry().setFromPoints(curve.getPoints(160)));
      const mat = track(new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending }));
      group.add(new THREE.Line(geo, mat));
    };
    loop(acp, 0xffc861, acpGroup);
    loop(vaa, 0xb06bff, vaaGroup);

    const coreGlowMat = track(new THREE.SpriteMaterial({ map: GLOW, color: 0x16d39a, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, opacity: 1 }));
    const coreGlow = new THREE.Sprite(coreGlowMat);
    coreGlow.scale.set(3.2, 3.2, 1);
    root.add(coreGlow);

    const planetTex = makePlanetTexture();
    const coreGeo = track(new THREE.SphereGeometry(0.62, 48, 48));
    const coreMat = track(new THREE.MeshStandardMaterial({ map: planetTex, color: 0xffffff, emissive: 0x05704f, emissiveIntensity: 0.5, roughness: 0.55, metalness: 0.12 }));
    const planet = new THREE.Mesh(coreGeo, coreMat);
    planet.rotation.z = 0.4;
    root.add(planet);

    const atmoGeo = track(new THREE.SphereGeometry(0.73, 40, 40));
    const atmoMat = track(new THREE.MeshBasicMaterial({ color: 0x33ffc4, transparent: true, opacity: 0.15, side: THREE.BackSide, blending: THREE.AdditiveBlending, depthWrite: false }));
    const atmosphere = new THREE.Mesh(atmoGeo, atmoMat);
    root.add(atmosphere);

    const ringGroup = new THREE.Group();
    const ringMat = track(new THREE.MeshBasicMaterial({ color: 0x3df0bd, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending }));
    const ring1Geo = track(new THREE.TorusGeometry(1.05, 0.02, 12, 96));
    ringGroup.add(new THREE.Mesh(ring1Geo, ringMat));
    const ring2Geo = track(new THREE.TorusGeometry(1.34, 0.014, 12, 110));
    ringGroup.add(new THREE.Mesh(ring2Geo, ringMat));
    ringGroup.rotation.x = Math.PI / 2.3;
    ringGroup.rotation.y = 0.18;
    root.add(ringGroup);

    if (studentName) {
      const nameLab = makeNameLabel(studentName);
      nameLab.position.set(0, -1.85, 0);
      root.add(nameLab);
    }

    let raf = null;
    let t = 0;
    const renderFrame = () => {
      renderer.render(scene, camera);
    };
    const animate = () => {
      raf = requestAnimationFrame(animate);
      t += 0.016;
      acpGroup.rotation.z += 0.0028;
      vaaGroup.rotation.y += 0.0024;
      sky.rotation.y += 0.0003;
      depth.rotation.y += 0.0004;
      planet.rotation.y += 0.012;
      const pulse = 1 + 0.04 * Math.sin(t * 1.6);
      atmosphere.scale.set(pulse, pulse, pulse);
      coreGlow.scale.set(3.2 * pulse, 3.2 * pulse, 1);
      for (let i = 0; i < twinkle.length; i++) {
        const tw = twinkle[i];
        const f = tw.base * (1 + 0.1 * Math.sin(t * 2 + tw.ph));
        tw.sp.scale.set(f, f, 1);
      }
      renderFrame();
    };
    if (reduced) renderFrame();
    else animate();

    const onResize = () => {
      width = mount.clientWidth || width;
      renderer.setSize(width, HEIGHT);
      camera.aspect = width / HEIGHT;
      camera.updateProjectionMatrix();
      if (reduced) renderFrame();
    };
    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
      if (raf) cancelAnimationFrame(raf);
      disposables.forEach((o) => {
        if (o && typeof o.dispose === 'function') o.dispose();
      });
      renderer.dispose();
      if (renderer.domElement && renderer.domElement.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
    };
  }, [profile, studentName]);

  return <div ref={mountRef} style={{ width: '100%', height: 460, borderRadius: 12, overflow: 'hidden' }} />;
}

export default SkillsConstellation;