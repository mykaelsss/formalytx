import type { LapTelemetryWithSession, SelectedLap } from "./types";

export const seriesKey = ({ year, event, session, driver, lap }: SelectedLap) =>
  `${year}:${event}:${session}:${driver}:${lap}`;

export const telemetryToSelected = (lap: LapTelemetryWithSession): SelectedLap => ({
  year: lap.year,
  event: lap.event,
  session: lap.session,
  driver: lap.driver,
  lap: lap.lap_number,
});
