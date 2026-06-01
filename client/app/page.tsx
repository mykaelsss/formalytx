'use client'
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { ChevronsUpDown } from "lucide-react";
import { CircleFlag } from 'react-circle-flags'
import Link from "next/link";
import { PodiumEntry, Schedule, ScheduleRound } from "@/lib/types";
import axios from "axios";

const YEARS = Array.from({ length: new Date().getFullYear() - 1949 }, (_, i) => String(new Date().getFullYear() - i));

const COUNTRY_ISO: Record<string, string> = {
  "Australia": "au", "Bahrain": "bh", "Saudi Arabia": "sa", "Japan": "jp",
  "China": "cn", "United States": "us", "USA": "us", "Italy": "it",
  "Monaco": "mc", "Canada": "ca", "Spain": "es", "Austria": "at",
  "United Kingdom": "gb", "Great Britain": "gb", "UK": "gb", "Hungary": "hu",
  "Belgium": "be", "Netherlands": "nl", "Azerbaijan": "az", "Singapore": "sg",
  "Mexico": "mx", "Brazil": "br", "Qatar": "qa", "UAE": "ae",
  "Abu Dhabi": "ae", "United Arab Emirates": "ae", "Germany": "de", "France": "fr",
  "Portugal": "pt", "Turkey": "tr", "Russia": "ru", "South Korea": "kr",
  "India": "in", "Argentina": "ar", "South Africa": "za", "Morocco": "ma",
  "Switzerland": "ch", "Sweden": "se",
};

const formatDateRange = (start: string, end: string) => {
  const s = new Date(start);
  const e = new Date(end);
  const months = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"];
  if (s.getMonth() === e.getMonth()) {
    return `${s.getDate()} - ${e.getDate()} ${months[e.getMonth()]}`;
  }
  return `${s.getDate()} ${months[s.getMonth()]} - ${e.getDate()} ${months[e.getMonth()]}`;
};


const FAKE_PODIUM: PodiumEntry[] = [
  { position: 1, code: "VER", time: "1:31:44.742" },
  { position: 2, code: "NOR", time: "+8.123s" },
  { position: 3, code: "LEC", time: "+15.456s" },
];

const FAKE_CIRCUIT = "M 20 80 C 40 80 40 40 80 40 C 120 40 140 20 160 20 C 180 20 190 40 190 60 C 190 80 170 90 150 90 C 130 90 110 100 90 110 C 70 120 50 120 30 110 C 15 100 10 90 20 80 Z";

export default function Home() {
  const [schedule, setSchedule] = useState<Schedule | undefined>();
  const [year, setYear] = useState<string>('2026');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const fetchSchedule = async () => {
      try {
        const res = await axios.get(`http://127.0.0.1:8000/schedule/${year}`);
        setSchedule(res.data);
      } catch(err) {
        console.error(err);
      }
    };
    fetchSchedule();
  }, [year]);

  return (
    <div className="min-h-full p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div className="flex flex-col items-end gap-1">
            <span className="text-gray-500 text-xs uppercase tracking-widest">Year</span>
            <Popover open={open} onOpenChange={setOpen}>
              <PopoverTrigger asChild>
                <Button variant="outline" className="w-36 bg-surface-card border-accent-red text-text-primary hover:bg-surface-card-hover hover:text-text-primary flex justify-between">
                  {year}
                  <ChevronsUpDown className="h-4 w-4 text-accent-red" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-36 p-0 bg-surface-card border-accent-red" align="end">
                <Command className="bg-surface-card">
                  <CommandInput placeholder="Search year..." className="text-text-primary" />
                  <CommandList>
                    <CommandEmpty className="text-gray-500 text-sm p-2">No results.</CommandEmpty>
                    <CommandGroup>
                      {YEARS.map(y => (
                        <CommandItem key={y} value={y} className="text-text-primary cursor-pointer" onSelect={(val) => { setYear(val); setOpen(false); }}>
                          {y}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {schedule?.rounds.map((round: ScheduleRound, idx) => (
            <Link key={idx} href={`/${year}/${round.round}`}>
              <Card className="bg-linear-to-b from-[#1f1f1f] to-surface-card border-l-4 border-l-accent-red border-t-0 border-r-0 border-b-0 hover:from-surface-border hover:to-[#161616] transition-colors cursor-pointer rounded-none flex flex-col justify-between min-h-56">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <span className="text-accent-red text-xs font-bold tracking-widest uppercase">Round {round.round}</span>
                    <span className="text-gray-500 text-xs">{formatDateRange(round.event_date_start, round.event_date_end)}</span>
                  </div>
                  <div className="space-y-2 mt-1">
                    <div className="flex gap-2 items-center">
                      <CircleFlag countryCode={COUNTRY_ISO[round.country] ?? "un"} height={18} width={18}/>
                      <CardTitle className="text-text-primary text-xl font-bold leading-tight">{round.event_name}</CardTitle>
                    </div>
                    <span className="text-gray-500 text-sm">{round.location}</span>
                  </div>
                </CardHeader>

                <CardContent className="flex flex-col gap-3">
                  <div className="flex items-end justify-between gap-4">
                    {round.status === 'completed' ? (
                      <div className="flex items-end gap-1 flex-1 min-w-0">
                        {/* 2nd */}
                        <div className="flex-1 flex flex-col items-center gap-1">
                          <span className="text-text-primary text-xs font-bold">{FAKE_PODIUM[1].code}</span>
                          <span className="text-gray-500 text-xs">{FAKE_PODIUM[1].time}</span>
                          <div className="w-full bg-surface-input h-8 flex items-center justify-center">
                            <span className="text-gray-400 text-xs font-bold">2ND</span>
                          </div>
                        </div>
                        {/* 1st */}
                        <div className="flex-1 flex flex-col items-center gap-1">
                          <span className="text-text-primary text-xs font-bold">{FAKE_PODIUM[0].code}</span>
                          <span className="text-gray-500 text-xs">{FAKE_PODIUM[0].time}</span>
                          <div className="w-full bg-accent-red-dark h-12 flex items-center justify-center">
                            <span className="text-text-primary text-xs font-bold">1ST</span>
                          </div>
                        </div>
                        {/* 3rd */}
                        <div className="flex-1 flex flex-col items-center gap-1">
                          <span className="text-text-primary text-xs font-bold">{FAKE_PODIUM[2].code}</span>
                          <span className="text-gray-500 text-xs">{FAKE_PODIUM[2].time}</span>
                          <div className="w-full bg-surface-card-hover h-6 flex items-center justify-center">
                            <span className="text-gray-400 text-xs font-bold">3RD</span>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <span className="text-accent-red text-xs font-bold tracking-widest uppercase">Upcoming</span>
                    )}
                    <svg viewBox="8 18 184 104" className="w-22 h-12 opacity-25 shrink-0 self-end">
                      <path d={FAKE_CIRCUIT} fill="none" stroke="white" strokeWidth="4" strokeLinejoin="round" strokeLinecap="round" />
                    </svg>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

      </div>
    </div>
  );
}
