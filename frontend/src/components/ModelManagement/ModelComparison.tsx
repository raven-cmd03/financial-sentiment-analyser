import { Cpu } from "lucide-react";
import type { ModelInfo } from "@/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import EmptyState from "@/components/common/EmptyState";

interface ModelComparisonProps {
  models: ModelInfo[];
}

export default function ModelComparison({ models }: ModelComparisonProps) {
  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2 space-y-0 pb-3">
        <Cpu className="h-4 w-4 text-primary" />
        <CardTitle className="text-sm">Available models</CardTitle>
      </CardHeader>
      <CardContent className="px-0 pb-0">
        {models.length === 0 ? (
          <div className="px-6 pb-6">
            <EmptyState
              icon={Cpu}
              title="No models available"
              description="Fine-tune a model to see it here."
            />
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Model</TableHead>
                <TableHead>Source</TableHead>
                <TableHead className="text-right">Accuracy</TableHead>
                <TableHead className="text-center">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {models.map((m) => (
                <TableRow
                  key={m.id}
                  className={m.is_active ? "bg-primary/5" : undefined}
                >
                  <TableCell className="font-medium text-foreground">
                    <div className="flex items-center gap-2">
                      <span>{m.name}</span>
                      {m.is_active && (
                        <Badge className="bg-primary/15 text-primary hover:bg-primary/15">
                          Active
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="capitalize text-muted-foreground">
                    {m.source}
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    {m.accuracy != null
                      ? `${(m.accuracy * 100).toFixed(1)}%`
                      : "—"}
                  </TableCell>
                  <TableCell className="text-center">
                    <span
                      className={
                        "inline-block h-2 w-2 rounded-full " +
                        (m.is_active ? "bg-positive" : "bg-muted-foreground/40")
                      }
                      aria-label={m.is_active ? "Active" : "Idle"}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
