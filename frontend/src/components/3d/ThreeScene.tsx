import { useEffect, useRef } from 'react';
import * as THREE from 'three';

export default function ThreeScene() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Scene setup
    const scene = new THREE.Scene();

    // Camera setup
    const camera = new THREE.PerspectiveCamera(
      45,
      container.clientWidth / container.clientHeight,
      0.1,
      1000
    );
    camera.position.z = 22;

    // Renderer setup
    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Group for mouse parallax rotation
    const group = new THREE.Group();
    scene.add(group);

    // 1. Core Geodesic Icosahedron (Obsidian Wireframe)
    const geoIcosahedron = new THREE.IcosahedronGeometry(6.5, 2);
    const matWireframe = new THREE.MeshBasicMaterial({
      color: 0x3a3a4c,
      wireframe: true,
      transparent: true,
      opacity: 0.35,
    });
    const icosahedronMesh = new THREE.Mesh(geoIcosahedron, matWireframe);
    group.add(icosahedronMesh);

    // 2. Inner Core (Deep Obsidian Sphere)
    const geoSphere = new THREE.SphereGeometry(4.2, 32, 32);
    const matSphere = new THREE.MeshStandardMaterial({
      color: 0x07070a,
      roughness: 0.2,
      metalness: 0.9,
    });
    const sphereMesh = new THREE.Mesh(geoSphere, matSphere);
    group.add(sphereMesh);

    // 3. Orbital Ring 1
    const geoTorus1 = new THREE.TorusGeometry(9.2, 0.03, 16, 100);
    const matTorus1 = new THREE.MeshBasicMaterial({
      color: 0x5a5a72,
      transparent: true,
      opacity: 0.45,
    });
    const torus1 = new THREE.Mesh(geoTorus1, matTorus1);
    torus1.rotation.x = Math.PI / 3;
    group.add(torus1);

    // 4. Orbital Ring 2
    const geoTorus2 = new THREE.TorusGeometry(10.5, 0.02, 16, 100);
    const matTorus2 = new THREE.MeshBasicMaterial({
      color: 0x3e3e54,
      transparent: true,
      opacity: 0.3,
    });
    const torus2 = new THREE.Mesh(geoTorus2, matTorus2);
    torus2.rotation.y = Math.PI / 4;
    group.add(torus2);

    // 5. Code Node Particle Field
    const particleCount = 180;
    const particleGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount * 3; i += 3) {
      const radius = 7.5 + Math.random() * 5.5;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);

      positions[i] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i + 2] = radius * Math.cos(phi);
    }

    particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const particleMat = new THREE.PointsMaterial({
      color: 0xa5a5be,
      size: 0.12,
      transparent: true,
      opacity: 0.65,
    });
    const particles = new THREE.Points(particleGeo, particleMat);
    group.add(particles);

    // Subtle Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const pointLight = new THREE.PointLight(0xffffff, 3.5, 50);
    pointLight.position.set(12, 16, 12);
    scene.add(pointLight);

    const backLight = new THREE.PointLight(0x404058, 2, 50);
    backLight.position.set(-12, -10, -10);
    scene.add(backLight);

    // Interactive mouse parallax
    let mouseX = 0;
    let mouseY = 0;
    let targetX = 0;
    let targetY = 0;

    const handleMouseMove = (event: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const x = event.clientX - rect.left - rect.width / 2;
      const y = event.clientY - rect.top - rect.height / 2;
      mouseX = (x / rect.width) * 0.8;
      mouseY = -(y / rect.height) * 0.8;
    };

    window.addEventListener('mousemove', handleMouseMove);

    // Animation Loop
    let animationFrameId: number;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      // Smooth damping rotation towards mouse position
      targetX += (mouseX - targetX) * 0.05;
      targetY += (mouseY - targetY) * 0.05;

      group.rotation.y += 0.003;
      group.rotation.x = targetY * 0.6;
      group.rotation.z = targetX * 0.4;

      icosahedronMesh.rotation.y += 0.002;
      torus1.rotation.z += 0.004;
      torus2.rotation.x += 0.003;
      particles.rotation.y -= 0.001;

      renderer.render(scene, camera);
    };

    animate();

    // Responsive Resize Handler
    const handleResize = () => {
      if (!container) return;
      const width = container.clientWidth;
      const height = container.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    // Cleanup
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      resizeObserver.disconnect();
      cancelAnimationFrame(animationFrameId);

      if (container && renderer.domElement && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }

      // Dispose resources
      geoIcosahedron.dispose();
      matWireframe.dispose();
      geoSphere.dispose();
      matSphere.dispose();
      geoTorus1.dispose();
      matTorus1.dispose();
      geoTorus2.dispose();
      matTorus2.dispose();
      particleGeo.dispose();
      particleMat.dispose();
      renderer.dispose();
    };
  }, []);

  return (
    <div 
      ref={containerRef} 
      className="relative w-full h-[300px] sm:h-[350px] md:h-[380px] flex items-center justify-center pointer-events-none"
    />
  );
}
