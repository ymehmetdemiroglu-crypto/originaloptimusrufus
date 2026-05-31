import { createClient } from "@/utils/supabase/server";
import { cookies } from "next/headers";

export default async function Page() {
  const cookieStore = await cookies();
  const supabase = createClient(cookieStore);

  const { data: todos, error } = await supabase.from("todos").select();

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-6 text-red-500">
        <h1 className="text-xl font-semibold mb-2">Error connecting to Supabase</h1>
        <p className="text-sm opacity-80">{error.message}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-lg">
        <h1 className="text-2xl font-bold tracking-tight mb-4 text-center">Supabase Todo List</h1>
        {(!todos || todos.length === 0) ? (
          <p className="text-sm text-muted-foreground text-center py-4">No todos found in 'todos' table.</p>
        ) : (
          <ul className="space-y-2">
            {todos.map((todo) => (
              <li
                key={todo.id}
                className="flex items-center gap-3 rounded-lg border border-border/60 bg-muted/30 px-4 py-3 text-sm font-medium transition-colors hover:bg-muted/50"
              >
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                <span>{todo.name}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
