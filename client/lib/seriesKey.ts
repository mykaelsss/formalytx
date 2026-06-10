import type { LapTelemetryWithSession, SelectedLap } from "./types";

export const seriesKey = ({ year, round, session, driver, lap }: SelectedLap) =>
  `${year}:${round}:${session}:${driver}:${lap}`;

export const telemetryToSelected = (lap: LapTelemetryWithSession): SelectedLap => ({
  year: lap.year,
  round: lap.round,
  session: lap.session,
  driver: lap.driver,
  lap: lap.lap_number,
});
