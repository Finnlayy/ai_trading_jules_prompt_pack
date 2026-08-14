import React, { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

export const ChartPanel: React.FC = () => {
    const chartContainerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!chartContainerRef.current) return;

        const chart = createChart(chartContainerRef.current, {
            width: chartContainerRef.current.clientWidth,
            height: 300,
            layout: {
                background: { color: '#151618' },
                textColor: '#d1d4dc',
            },
            grid: {
                vertLines: { color: 'rgba(42, 46, 57, 0.5)' },
                horzLines: { color: 'rgba(42, 46, 57, 0.5)' },
            },
        });

        // Use addLineSeries which is the typical lightweight-charts v4 API
        const lineSeries = (chart as any).addLineSeries({
            color: '#3ebd93',
        });

        // Dummy data
        lineSeries.setData([
            { time: '2023-01-01', value: 100 },
            { time: '2023-01-02', value: 105 },
            { time: '2023-01-03', value: 102 },
        ]);

        return () => {
            chart.remove();
        };
    }, []);

    return <div ref={chartContainerRef} style={{ width: '100%' }} />;
};
