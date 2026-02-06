'use client';

import { useEffect, useRef } from 'react';
import { useTheme } from '@/context/ThemeContext';

interface Point {
    x: number;
    y: number;
    vx: number;
    vy: number;
}

export function NeuralLattice() {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const { theme } = useTheme();

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        let animationFrameId: number;
        let points: Point[] = [];
        const POINT_COUNT = 50;
        const CONNECTION_DISTANCE = 180;

        // Theme-aware colors
        const isDark = theme === 'dark';
        const COLOR_ACCENT = isDark ? '57, 255, 20' : '57, 255, 20'; // Neon green both themes
        const COLOR_LINE = isDark ? '34, 211, 238' : '0, 0, 0'; // Cyan in dark, black in light
        const POINT_OPACITY = isDark ? 0.6 : 0.3;
        const LINE_OPACITY = isDark ? 0.15 : 0.04;

        const resize = () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        };

        const initPoints = () => {
            points = [];
            for (let i = 0; i < POINT_COUNT; i++) {
                points.push({
                    x: Math.random() * canvas.width,
                    y: Math.random() * canvas.height,
                    vx: (Math.random() - 0.5) * 0.4,
                    vy: (Math.random() - 0.5) * 0.4,
                });
            }
        };

        const draw = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Update and draw points
            points.forEach((point, i) => {
                point.x += point.vx;
                point.y += point.vy;

                // Bounce off edges
                if (point.x < 0 || point.x > canvas.width) point.vx *= -1;
                if (point.y < 0 || point.y > canvas.height) point.vy *= -1;

                // Draw Point
                ctx.beginPath();
                ctx.arc(point.x, point.y, 2, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(${COLOR_ACCENT}, ${POINT_OPACITY})`;
                ctx.fill();

                // Draw connections
                for (let j = i + 1; j < points.length; j++) {
                    const other = points[j];
                    const dx = point.x - other.x;
                    const dy = point.y - other.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);

                    if (distance < CONNECTION_DISTANCE) {
                        ctx.beginPath();
                        ctx.moveTo(point.x, point.y);
                        ctx.lineTo(other.x, other.y);
                        const opacity = 1 - distance / CONNECTION_DISTANCE;
                        ctx.strokeStyle = `rgba(${COLOR_LINE}, ${opacity * LINE_OPACITY})`;
                        ctx.lineWidth = 1;
                        ctx.stroke();
                    }
                }
            });

            animationFrameId = requestAnimationFrame(draw);
        };

        window.addEventListener('resize', resize);
        resize();
        initPoints();
        draw();

        return () => {
            window.removeEventListener('resize', resize);
            cancelAnimationFrame(animationFrameId);
        };
    }, [theme]);

    return (
        <canvas
            ref={canvasRef}
            className="fixed top-0 left-0 w-full h-full pointer-events-none z-0 opacity-50"
        />
    );
}
