'use client'

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Result, RoundSchedule } from "@/lib/types";
import axios from "axios";
import { use, useEffect, useState } from "react";

function formatDate(date: string) {
    const [, , day] = date.split('-');
    return {
        day,
        month: new Date(date).toLocaleString("en-US", { month: 'short' }).toUpperCase()
    }
}

function StatusBadge({ status }: { status: string }) {
    return (
        <span className={`text-xs font-bold uppercase tracking-widest ${status === 'completed' ? 'text-status-completed' : 'text-status-upcoming'}`}>
            {status}
        </span>
    );
}

const POSITION_COLORS: Record<number, string> = {
    1: "text-[#FFD700]",
    2: "text-[#C0C0C0]",
    3: "text-[#CD7F32]",
};

type ResultIdentifier = 'R' | 'FP1' | 'FP2' | 'FP3' | 'Q' | 'SQ' | 'S'

export default function RoundPage({ params }: { params: Promise<{ year: string; round: string }> }) {
    const { year, round } = use(params);
    const [roundSchedule, setRoundSchedule] = useState<RoundSchedule>();
    const [results, setResults] = useState<Result[]>();
    const [resultIdentifier, setResultIdentifier] = useState<ResultIdentifier>('R')

    useEffect(() => {
        const fetchRoundSchedule = async () => {
            const res = await fetch(`http://127.0.0.1:8000/schedule/${year}/${round}`);
            setRoundSchedule(await res.json());
        };
        fetchRoundSchedule();
    }, [round, year]);

    useEffect(() => {
        const fetchResults = async () => {
            try {
                const res = await axios.get(`http://127.0.0.1:8000/schedule/${year}/${round}/${resultIdentifier}/results`);
                setResults(res.data);
            } catch(err) {
                console.error(err)
            }
        };
        fetchResults();
    }, [round, year, resultIdentifier]);

    return (
        <div className="min-h-screen bg-surface-base">
            <header className="relative w-full h-12 overflow-hidden flex items-center px-8">
                <div className="absolute inset-0" style={{ backgroundImage: "repeating-conic-gradient(#888 0% 25%, #333 0% 50%)", backgroundSize: "36px 36px", opacity: 0.6 }} />
                <div className="absolute inset-0 bg-black/60" />
                <div className="absolute left-0 top-0 h-full w-1 bg-accent-red" />
                <div className="relative z-10 flex items-baseline gap-4">
                    <span className="text-accent-red text-lg font-bold tracking-widest uppercase">Round {round}</span>
                    <span className="text-text-primary text-2xl">-</span>
                    <span className="text-text-primary tracking-widest">{year}</span>
                </div>
            </header>

            <div className="max-w-7xl mx-auto p-8 flex flex-col gap-12">

                <div className="flex flex-col gap-3 relative">
                    <div className="absolute left-1.75 top-2 bottom-2 w-px bg-surface-border" />
                    {roundSchedule?.sessions.map((s, id) => {
                        const date = formatDate(s.date);
                        return (
                            <div key={id} className="flex items-center gap-6 relative">
                                <div className={`w-4 h-4 rounded-full shrink-0 border-2 z-10 ${s.status === 'completed' ? 'bg-accent-red border-accent-red' : 'bg-surface-base border-surface-border'}`} />
                                <div className="flex-1 flex items-center gap-8 py-4 px-4 bg-surface-card hover:bg-surface-card-hover cursor-pointer transition-colors">
                                    <div className="flex flex-col gap-0 w-6 shrink-0 text-text-primary">
                                        <span className="font-bold block">{date.day}</span>
                                        <span className="text-xs">{date.month}</span>
                                    </div>
                                    <div className="w-px h-8 bg-surface-border shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <span className="text-text-primary font-bold uppercase tracking-wide text-sm block">{s.name}</span>
                                        <div className="flex items-center gap-3">
                                            <span className="text-text-muted text-xs">{s.start_time} - {s.end_time}</span>
                                            {s.fastest_lap && <>
                                                <span className="text-surface-border">·</span>
                                                <span className="text-text-muted text-xs">Fastest</span>
                                                <span className="text-text-secondary text-xs">{s.fastest_lap}</span>
                                            </>}
                                        </div>
                                    </div>
                                    <div className="flex items-center text-text-secondary text-xs gap-0.5 shrink-0">
                                        {s.weather && <><span>{s.weather.air_temp}</span><span>°C</span></>}
                                    </div>
                                    <StatusBadge status={s.status} />
                                </div>
                            </div>
                        );
                    })}
                </div>
                
                <section className="space-y-1">
                    <div className="flex justify-between">
                        <h1 className="text-text-primary text-2xl">Results</h1>
                        <Select value={resultIdentifier} onValueChange={(val) => setResultIdentifier(val as ResultIdentifier)}>
                            <SelectTrigger className="w-full max-w-48 text-text-primary">
                                <SelectValue placeholder="Results" />
                            </SelectTrigger>
                            <SelectContent side="bottom" className="bg-surface-card">
                                <SelectGroup>
                                <SelectLabel>Results</SelectLabel>
                                {roundSchedule?.sessions.map((s, idx) => {
                                    return (
                                        <SelectItem key={idx} className="text-text-primary" value={s.identifier}>{s.name}</SelectItem>
                                    )
                                })}
                                </SelectGroup>
                            </SelectContent>
                        </Select>
                    </div>
                    {results && results.length > 0 && (
                        <div className="w-full">
                            <div className="flex flex-col divide-y divide-surface-border">
                                {results.map(r => (
                                    <div key={r.code} className="flex items-center gap-6 py-3 px-2 hover:bg-surface-card transition-colors">
                                        <span className={`w-6 text-sm font-bold shrink-0 tabular-nums ${POSITION_COLORS[r.position] ?? 'text-text-muted'}`}>{r.position}</span>
                                        <div className="w-1 h-8 shrink-0 rounded-full" style={{ background: `#${r.team_color}` }} />
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <span className="text-text-primary font-bold text-sm">{r.code}</span>
                                                <span className="text-text-muted text-xs hidden sm:inline">{r.full_name}</span>
                                            </div>
                                            <span className="text-text-muted text-xs">{r.team}</span>
                                        </div>
                                        <span className="text-text-muted text-xs shrink-0 hidden md:block">P{r.grid} → P{r.position}</span>
                                        <span className="font-mono text-xs shrink-0 w-28 text-right">
                                            {r.time === null && !r.q1 && !r.q2 && !r.q3 ? (
                                                <span className="text-accent-red">DNF</span>
                                            ) : (
                                                <span className="text-text-secondary">{r.q3 ?? r.q2 ?? r.q1 ?? r.time}</span>
                                            )}
                                        </span>
                                        <span className="text-text-muted text-xs w-8 text-right shrink-0">
                                            {r.points > 0 ? <span className="text-text-primary">{r.points}</span> : '—'}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </section>
            </div>
        </div>
    );
}
