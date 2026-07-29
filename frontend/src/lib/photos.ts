import type { ImageRole, Kind } from "../api/client";

// `capture` only means anything on a device with a real camera; on a desktop it would just be a
// second file dialog. `navigator.mediaDevices` is no help here because it is undefined over plain
// HTTP, which is how a LAN install is served.
export const HAS_CAMERA =
  typeof window !== "undefined" && window.matchMedia("(pointer: coarse)").matches;

export function rolesFor(kind: Kind): [ImageRole, ImageRole] {
  return kind === "banknote" ? ["face", "back"] : ["obverse", "reverse"];
}
