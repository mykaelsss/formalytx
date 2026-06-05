import { useEffect, useRef } from "react";
import { init } from "echarts";

export function useEcharts() {
  const chartRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    const el = chartRef.current;
    if (!el) return;
    const instance = init(el);
    if (!instance) return;
    const ro = new ResizeObserver(() => instance.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
      instance.dispose();
    };
  }, []);

  return chartRef;
}
