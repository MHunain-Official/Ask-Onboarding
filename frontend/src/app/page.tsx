import { redirect } from "next/navigation";

// The app lives under /chat; the (app) layout sends signed-out users to /login.
export default function HomePage(): never {
  redirect("/chat");
}
