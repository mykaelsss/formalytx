import { useEffect, useRef } from "react";
import { init } from "echarts";

export function useEcharts() {
  const chartRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
      const el = chartRef.current;
      if (!el) return;

      const instance = init(el);
      const ro = new ResizeObserver(() => {
        if (el.clientWidth === 0 || el.clientHeight === 0) return;
        instance.resize();
      });
      ro.observe(el);

      return () => {
        ro.disconnect();
        instance.dispose();
      };
    }, []);

  return chartRef;
}
