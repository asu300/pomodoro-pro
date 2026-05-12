import { useState, useEffect, useRef, useCallback } from 'react';
import { sendNotification } from '@tauri-apps/plugin-notification';
import { Store } from '@tauri-apps/plugin-store';
import './index.css';

type TimerMode = 'work' | 'shortBreak' | 'longBreak';

const MODES: Record<TimerMode, { label: string; minutes: number; color: string; bgColor: string }> = {
  work: { label: '专注', minutes: 25, color: '#e74c3c', bgColor: '#fdeaea' },
  shortBreak: { label: '短休息', minutes: 5, color: '#27ae60', bgColor: '#e9f7ef' },
  longBreak: { label: '长休息', minutes: 15, color: '#3498db', bgColor: '#eaf2f8' },
};

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function getTodayKey(): string {
  return new Date().toISOString().split('T')[0];
}

export default function App() {
  const [mode, setMode] = useState<TimerMode>('work');
  const [timeLeft, setTimeLeft] = useState(MODES.work.minutes * 60);
  const [isRunning, setIsRunning] = useState(false);
  const [todayCount, setTodayCount] = useState(0);
  const [sessionCount, setSessionCount] = useState(0);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const storeRef = useRef<Store | null>(null);
  const stateRef = useRef({ mode, timeLeft, isRunning, todayCount, sessionCount });

  useEffect(() => {
    stateRef.current = { mode, timeLeft, isRunning, todayCount, sessionCount };
  }, [mode, timeLeft, isRunning, todayCount, sessionCount]);

  // Load persisted data
  useEffect(() => {
    let mounted = true;
    Store.load('settings.json').then((store) => {
      if (!mounted) return;
      storeRef.current = store;
      store.get<string>('lastDate').then((savedDate) => {
        if (!mounted) return;
        const today = getTodayKey();
        if (savedDate === today) {
          store.get<number>('todayCount').then((c) => {
            if (mounted) setTodayCount(c || 0);
          });
        } else {
          store.set('lastDate', today);
          store.set('todayCount', 0);
          store.save();
        }
      });
    });
    return () => { mounted = false; };
  }, []);

  // Timer interval
  useEffect(() => {
    if (isRunning) {
      intervalRef.current = setInterval(() => {
        setTimeLeft((prev) => {
          if (prev <= 1) {
            if (intervalRef.current) {
              clearInterval(intervalRef.current);
              intervalRef.current = null;
            }
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isRunning]);

  // Handle completion when timeLeft reaches 0
  useEffect(() => {
    if (timeLeft !== 0) {
      document.title = `${formatTime(timeLeft)} - ${MODES[mode].label}`;
      return;
    }

    const { mode: currentMode, todayCount: tc, sessionCount: sc } = stateRef.current;
    setIsRunning(false);

    if (currentMode === 'work') {
      const newCount = tc + 1;
      const newSession = sc + 1;
      setTodayCount(newCount);
      setSessionCount(newSession);

      if (storeRef.current) {
        storeRef.current.set('todayCount', newCount);
        storeRef.current.set('lastDate', getTodayKey());
        storeRef.current.save();
      }

      sendNotification({ title: '专注完成', body: '很棒！休息一下吧。' });

      if (newSession % 4 === 0) {
        setMode('longBreak');
        setTimeLeft(MODES.longBreak.minutes * 60);
        document.title = `${MODES.longBreak.label} - ${formatTime(MODES.longBreak.minutes * 60)}`;
      } else {
        setMode('shortBreak');
        setTimeLeft(MODES.shortBreak.minutes * 60);
        document.title = `${MODES.shortBreak.label} - ${formatTime(MODES.shortBreak.minutes * 60)}`;
      }
    } else {
      sendNotification({ title: '休息结束', body: '准备好开始新的专注了吗？' });
      setMode('work');
      setTimeLeft(MODES.work.minutes * 60);
      document.title = `${MODES.work.label} - ${formatTime(MODES.work.minutes * 60)}`;
    }
  }, [timeLeft, mode]);

  const switchMode = useCallback((newMode: TimerMode) => {
    setIsRunning(false);
    setMode(newMode);
    setTimeLeft(MODES[newMode].minutes * 60);
    document.title = `${MODES[newMode].label} - ${formatTime(MODES[newMode].minutes * 60)}`;
  }, []);

  const toggleTimer = useCallback(() => {
    setIsRunning((prev) => !prev);
  }, []);

  const resetTimer = useCallback(() => {
    setIsRunning(false);
    setTimeLeft(MODES[mode].minutes * 60);
  }, [mode]);

  const skipTimer = useCallback(() => {
    setIsRunning(false);
    setTimeLeft(0);
  }, []);

  const totalSeconds = MODES[mode].minutes * 60;
  const progress = totalSeconds > 0 ? ((totalSeconds - timeLeft) / totalSeconds) * 100 : 0;
  const radius = 110;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (progress / 100) * circumference;

  const modeInfo = MODES[mode];

  return (
    <div className="app" style={{ background: modeInfo.bgColor }}>
      <div className="container">
        <div className="mode-tabs">
          {(Object.keys(MODES) as TimerMode[]).map((m) => (
            <button
              key={m}
              className={`mode-tab ${mode === m ? 'active' : ''}`}
              onClick={() => switchMode(m)}
              style={{
                color: mode === m ? modeInfo.color : undefined,
                background: mode === m ? modeInfo.bgColor : undefined,
              }}
            >
              {MODES[m].label}
            </button>
          ))}
        </div>

        <div className="timer-display">
          <svg className="progress-ring" width="260" height="260" viewBox="0 0 260 260">
            <circle
              className="progress-ring-bg"
              cx="130"
              cy="130"
              r={radius}
            />
            <circle
              className="progress-ring-fill"
              cx="130"
              cy="130"
              r={radius}
              stroke={modeInfo.color}
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
            />
          </svg>
          <div className="time-text">{formatTime(timeLeft)}</div>
        </div>

        <div className="controls">
          <button className="btn btn-secondary" onClick={resetTimer}>
            重置
          </button>
          <button
            className="btn btn-primary"
            onClick={toggleTimer}
            style={{ background: modeInfo.color }}
          >
            {isRunning ? '暂停' : '开始'}
          </button>
          <button className="btn btn-secondary" onClick={skipTimer}>
            跳过
          </button>
        </div>

        <div className="stats">
          <div className="stat">
            <span className="stat-value" style={{ color: modeInfo.color }}>
              {todayCount}
            </span>
            <span className="stat-label">今日番茄</span>
          </div>
          <div className="stat">
            <span className="stat-value" style={{ color: modeInfo.color }}>
              {sessionCount % 4 === 0 && sessionCount > 0 ? 4 : sessionCount % 4 || 0}
            </span>
            <span className="stat-label">当前轮次</span>
          </div>
        </div>
      </div>
    </div>
  );
}
