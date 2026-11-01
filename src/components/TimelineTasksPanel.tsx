import React, { useState } from 'react';
import { TimelineTask, ServiceCategory, VendorPriceRecord } from '../types/intelligence';
import { CATEGORY_LABELS } from '../utils/ledgerMath';
import {
  Plus,
  Trash2,
  Calendar,
  Check,
  ListTodo,
} from 'lucide-react';

interface TimelineTasksPanelProps {
  tasks: TimelineTask[];
  vendors: VendorPriceRecord[];
  onUpdateStatus: (taskId: string, status: TimelineTask['status']) => void;
  onAddTask: (task: Omit<TimelineTask, 'id'>) => void;
  onDeleteTask: (taskId: string) => void;
}

export const TimelineTasksPanel: React.FC<TimelineTasksPanelProps> = ({
  tasks,
  vendors,
  onUpdateStatus,
  onAddTask,
  onDeleteTask,
}) => {
  const [isAdding, setIsAdding] = useState(false);
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState<ServiceCategory>('venue');
  const [dueDate, setDueDate] = useState('2026-11-10');
  const [priority, setPriority] = useState<TimelineTask['priority']>('medium');

  const handleAddSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    onAddTask({
      title: title.trim(),
      category,
      dueDate,
      priority,
      status: 'todo',
    });

    setTitle('');
    setIsAdding(false);
  };

  const completedCount = tasks.filter((t) => t.status === 'done').length;

  return (
    <div className="bg-white border-2 border-black rounded-2xl overflow-hidden shadow-[4px_4px_0px_0px_#000]">
      {/* Header */}
      <div className="p-4 sm:p-5 bg-[#FFE600] border-b-2 border-black flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-white border-2 border-black flex items-center justify-center text-sm shadow-[1px_1px_0px_0px_#000]">
              📋
            </div>
            <h3 className="text-base font-black text-black tracking-tight">
              Event Milestones & Checklist
            </h3>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-white border-2 border-black text-black font-black shadow-[1px_1px_0px_0px_#000]">
              {completedCount} of {tasks.length} done
            </span>
          </div>
          <p className="text-xs font-semibold text-black/80 mt-1">
            Track deposit schedules, tastings, license approvals, and final run-throughs
          </p>
        </div>

        <button
          onClick={() => setIsAdding(!isAdding)}
          className="flex items-center gap-1.5 text-xs font-black text-black bg-[#FF6B8B] hover:bg-pink-400 px-3.5 py-1.5 rounded-lg border-2 border-black shadow-[2px_2px_0px_0px_#000] transition-transform active:translate-x-0.5 active:translate-y-0.5"
        >
          <Plus className="w-3.5 h-3.5 stroke-[3]" />
          <span>Add Task</span>
        </button>
      </div>

      {/* Inline Add Task Form */}
      {isAdding && (
        <form
          onSubmit={handleAddSubmit}
          className="p-4 border-b-2 border-black bg-[#F8F5EE] space-y-3 animate-in fade-in duration-150"
        >
          <div>
            <label className="block text-xs font-black uppercase text-black mb-1">
              Task Description
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Sign catering agreement & pay 20% advance"
              className="w-full bg-white border-2 border-black rounded-lg px-3 py-2 text-xs font-bold text-black placeholder-black/40 focus:outline-none shadow-[2px_2px_0px_0px_#000]"
              autoFocus
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-black uppercase text-black mb-1">
                Category
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as ServiceCategory)}
                className="w-full bg-white border-2 border-black rounded-lg px-3 py-1.5 text-xs font-bold text-black focus:outline-none shadow-[2px_2px_0px_0px_#000]"
              >
                {(Object.keys(CATEGORY_LABELS) as ServiceCategory[]).map(
                  (cat) => (
                    <option key={cat} value={cat}>
                      {CATEGORY_LABELS[cat]}
                    </option>
                  )
                )}
              </select>
            </div>

            <div>
              <label className="block text-xs font-black uppercase text-black mb-1">
                Due Date
              </label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full bg-white border-2 border-black rounded-lg px-3 py-1.5 text-xs font-bold text-black focus:outline-none shadow-[2px_2px_0px_0px_#000]"
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setIsAdding(false)}
              className="px-3 py-1.5 rounded-lg text-xs font-black text-black bg-white border-2 border-black shadow-[1px_1px_0px_0px_#000]"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="bg-[#4ADE80] text-black font-black px-4 py-1.5 rounded-lg text-xs border-2 border-black shadow-[2px_2px_0px_0px_#000] hover:bg-[#22c55e]"
            >
              Save Milestone
            </button>
          </div>
        </form>
      )}

      {/* Task List */}
      {tasks.length === 0 ? (
        <div className="p-8 text-center text-black/60 font-bold text-xs bg-[#FFFDF9]">
          No tasks added yet. Click "+ Add Task" to schedule vendor milestones.
        </div>
      ) : (
        <div className="divide-y-2 divide-black bg-[#FFFDF9]">
          {tasks.map((task) => {
            const isDone = task.status === 'done';

            return (
              <div
                key={task.id}
                className={`p-3.5 sm:px-5 flex items-center justify-between gap-3 transition-colors hover:bg-[#F8F5EE] ${
                  isDone ? 'bg-[#F8F5EE]/60' : ''
                }`}
              >
                {/* Toggle Completion */}
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <button
                    onClick={() =>
                      onUpdateStatus(task.id, isDone ? 'todo' : 'done')
                    }
                    className={`w-5 h-5 rounded-md flex items-center justify-center transition-transform active:scale-95 shrink-0 border-2 border-black shadow-[1px_1px_0px_0px_#000] ${
                      isDone
                        ? 'bg-[#4ADE80] text-black'
                        : 'bg-white hover:bg-yellow-100'
                    }`}
                  >
                    {isDone && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                  </button>

                  <div className="min-w-0">
                    <p
                      className={`text-xs font-black truncate ${
                        isDone ? 'line-through text-black/40' : 'text-black'
                      }`}
                    >
                      {task.title}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5 text-[11px] font-bold text-black/70">
                      <span className="bg-[#BAE6FD] text-black px-1.5 py-0.2 rounded border border-black text-[10px]">
                        {CATEGORY_LABELS[task.category]}
                      </span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-black/60" />
                        {task.dueDate}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Delete button */}
                <button
                  onClick={() => onDeleteTask(task.id)}
                  className="p-1.5 text-black hover:text-red-600 hover:bg-red-100 rounded-lg border-2 border-transparent hover:border-black transition-colors"
                  title="Delete task"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
