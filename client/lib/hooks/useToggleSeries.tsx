import { getInstanceByDom } from 'echarts';
import { useCallback } from 'react';
import type { Dispatch, RefObject, SetStateAction } from 'react';

export function useToggleSeries(hiddenSeries: Set<string>, setHiddenSeries: Dispatch<SetStateAction<Set<string>>>, chartRef: RefObject<HTMLDivElement | null>) {
    return useCallback((name: string) => {
      if (!chartRef.current) return;
      const chart = getInstanceByDom(chartRef.current);
      if (!chart) return;
      const isHidden = hiddenSeries.has(name);
      chart.dispatchAction({
        type: isHidden ? "legendSelect" : "legendUnSelect",
        name,
      });
      setHiddenSeries((prev) => {
        const next = new Set(prev);
        if (isHidden) next.delete(name);
        else next.add(name);
        return next;
      });
    }, [hiddenSeries, setHiddenSeries, chartRef])
}