import { useZendaya } from "../../store/zendayaStore";

/** A small corner pill shown while the HUD isn't connected to the backend, so the
 *  boot handshake and any crash-restart reconnect window read as intentional
 *  rather than broken. Hidden once connected. */
export default function ConnectionStatus() {
  const connected = useZendaya((s) => s.connected);
  if (connected) return null;
  return (
    <div className="zen-conn-status" data-testid="connection-status" role="status">
      connecting…
    </div>
  );
}
