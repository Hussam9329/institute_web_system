import React, { useState, useEffect } from 'react';
import './App.css';
import LoginScreen from './components/LoginScreen';
import Dashboard from './components/Dashboard';
import { loadFromStorage, saveToStorage } from './utils/storage';

function App() {
  const [isLocked, setIsLocked] = useState(true);
  const [students, setStudents] = useState(() => loadFromStorage('students') || []);
  const [subjects, setSubjects] = useState(() => loadFromStorage('subjects') || []);
  const [teachers, setTeachers] = useState(() => loadFromStorage('teachers') || []);
  const [payments, setPayments] = useState(() => loadFromStorage('payments') || []);
  const [settings, setSettings] = useState(() => loadFromStorage('settings') || {});

  useEffect(() => {
    saveToStorage('students', students);
  }, [students]);

  useEffect(() => {
    saveToStorage('subjects', subjects);
  }, [subjects]);

  useEffect(() => {
    saveToStorage('teachers', teachers);
  }, [teachers]);

  useEffect(() => {
    saveToStorage('payments', payments);
  }, [payments]);

  useEffect(() => {
    saveToStorage('settings', settings);
  }, [settings]);

  const handleLogin = (code) => {
    if (code === '1111') {
      setIsLocked(false);
      return true;
    }
    return false;
  };

  if (isLocked) {
    return <LoginScreen onLogin={handleLogin} />;
  }

  return (
    <Dashboard
      students={students}
      setStudents={setStudents}
      subjects={subjects}
      setSubjects={setSubjects}
      teachers={teachers}
      setTeachers={setTeachers}
      payments={payments}
      setPayments={setPayments}
      settings={settings}
      setSettings={setSettings}
    />
  );
}

export default App;
