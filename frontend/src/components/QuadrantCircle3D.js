import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

function QuadrantCircle3D({ size = 300 }) {
  const mountRef = useRef(null);

  useEffect(() => {
    if (!mountRef.current) return;

    // Scene setup
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    
    renderer.setSize(size, size);
    renderer.setClearColor(0x000000, 0);
    mountRef.current.appendChild(renderer.domElement);

    camera.position.z = 5;

    // Create quadrant colors
    const colors = [
      0xE74C3C, // Academic - Red
      0x9B59B6, // Internship - Purple
      0x2ECC71, // National Identity - Green
      0xF39C12, // Leadership - Orange
    ];

    // Create circular segments
    const group = new THREE.Group();
    const radius = 2;
    const segments = 4;

    for (let i = 0; i < segments; i++) {
      const startAngle = (i * Math.PI * 2) / segments;
      const endAngle = ((i + 1) * Math.PI * 2) / segments;

      const shape = new THREE.Shape();
      shape.moveTo(0, 0);
      shape.arc(0, 0, radius, startAngle, endAngle, false);
      shape.lineTo(0, 0);

      const geometry = new THREE.ShapeGeometry(shape);
      const material = new THREE.MeshBasicMaterial({
        color: colors[i],
        side: THREE.DoubleSide,
      });
      
      const mesh = new THREE.Mesh(geometry, material);
      group.add(mesh);

      // Add outline
      const edges = new THREE.EdgesGeometry(geometry);
      const line = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 2 })
      );
      group.add(line);
    }

    scene.add(group);

    // Animation
    let animationId;
    const animate = () => {
      animationId = requestAnimationFrame(animate);
      group.rotation.z += 0.005;
      renderer.render(scene, camera);
    };
    animate();

    // Cleanup
    return () => {
      cancelAnimationFrame(animationId);
      if (mountRef.current && renderer.domElement) {
        mountRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, [size]);

  return <div ref={mountRef} style={{ width: size, height: size }} />;
}

export default QuadrantCircle3D;