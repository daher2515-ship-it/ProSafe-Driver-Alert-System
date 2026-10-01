
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
import requests
import threading
import time

# الاتصال بقاعدة البيانات
conn = sqlite3.connect("distractions.db")
cursor = conn.cursor()

# الواجهة
root = tk.Tk()
root.title("سجل حالات التشتت")
root.geometry("1400x650")

tk.Label(root, text="سجل حالات التشتت", font=("Arial", 16, "bold")).pack(pady=10)

columns = ("id", "type", "start_time", "end_time", "duration", "location")
tree = ttk.Treeview(root, columns=columns, show="headings")

for col in columns:
    tree.heading(col, text=col if col != "type" else "النوع")
    tree.column(col, width=120, anchor="center")

tree.pack(expand=True, fill="both", padx=10, pady=10)

# إطار الإحصائيات
stats_frame = tk.Frame(root, bg="#f0f0f0", padx=10, pady=5)
stats_frame.pack(side="bottom", fill="x", padx=10, pady=10, anchor="sw")

def update_stats():
    for widget in stats_frame.winfo_children():
        widget.destroy()

    tk.Label(stats_frame, text="الإحصائيات:", font=("Arial", 12, "bold"), bg="#f0f0f0").grid(row=0, column=0, sticky="w", columnspan=2)

    cursor.execute("SELECT COUNT(*) FROM distractions")
    total_cases = cursor.fetchone()[0]

    cursor.execute("SELECT type, COUNT(*), SUM(duration) FROM distractions GROUP BY type")
    stats = cursor.fetchall()

    row = 1
    tk.Label(stats_frame, text=f"العدد الإجمالي للحالات: {total_cases}", font=("Arial", 11, "bold"), bg="#f0f0f0").grid(row=row, column=0, sticky="w", columnspan=2)
    row += 1
    tk.Label(stats_frame, text="-"*50, bg="#f0f0f0").grid(row=row, column=0, sticky="w", columnspan=2)
    row += 1
    tk.Label(stats_frame, text="التفاصيل حسب النوع:", font=("Arial", 11), bg="#f0f0f0").grid(row=row, column=0, sticky="w")
    row += 1

    for stat in stats:
        type_, count, total_duration = stat
        tk.Label(stats_frame, text=f"• {type_}:النوع", font=("Arial", 10), bg="#f0f0f0").grid(row=row, column=0, sticky="w")
        tk.Label(stats_frame, text=f"عدد الحالات: {count}  المدة الإجمالية: {total_duration:.2f} ثانية", font=("Arial", 10), bg="#f0f0f0").grid(row=row, column=1, sticky="w")
        row += 1

def load_data(filter_type=None):
    for item in tree.get_children():
        tree.delete(item)
    if filter_type and filter_type != "الكل":
        cursor.execute("SELECT id, type, start_time, end_time, duration, location FROM distractions WHERE type=?", (filter_type,))
    else:
        cursor.execute("SELECT id, type, start_time, end_time, duration, location FROM distractions ORDER BY id DESC")
    for row in cursor.fetchall():
        tree.insert("", tk.END, values=row)
    update_stats()

filter_frame = tk.Frame(root)
filter_frame.pack(pady=5)

tk.Label(filter_frame, text="فلترة حسب النوع:").pack(side="left", padx=5)
filter_var = tk.StringVar()
filter_combo = ttk.Combobox(filter_frame, textvariable=filter_var, state="readonly")
filter_combo["values"] = ["الكل", "eyes_closed", "head_pose", "yawning", "distracted_hands"]
filter_combo.current(0)
filter_combo.pack(side="left", padx=5)

tk.Button(filter_frame, text="فلترة", command=lambda: load_data(filter_var.get())).pack(side="left", padx=5)
tk.Button(filter_frame, text="تحديث الكل", command=load_data).pack(side="left", padx=5)

def delete_selected():
    selected = tree.selection()
    if not selected:
        messagebox.showwarning("تحذير", "حدد حالة أولًا.")
        return
    item = tree.item(selected)
    id_ = item["values"][0]
    if messagebox.askyesno("تأكيد", "هل تريد حذف الحالة؟"):
        cursor.execute("DELETE FROM distractions WHERE id=?", (id_,))
        conn.commit()
        load_data(filter_var.get())
        messagebox.showinfo("تم", "تم الحذف بنجاح")

def delete_all():
    if messagebox.askyesno("تأكيد", "هل تريد حذف جميع الحالات؟"):
        cursor.execute("DELETE FROM distractions")
        conn.commit()
        load_data()
        messagebox.showinfo("تم", "تم حذف جميع الحالات بنجاح")

def generate_daily_report(save_as=False):
    now = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    cursor.execute("SELECT * FROM distractions WHERE start_time LIKE ?", (f'{now[:10]}%',))
    records = cursor.fetchall()
    if not records:
        messagebox.showinfo("لا يوجد", "لا توجد حالات اليوم.")
        return

    if save_as:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialfile=f"daily_report_{now}.txt"
        )
        if not file_path:
            return
    else:
        file_path = f"daily_report_{now}.txt"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"Dispersion Report- {now}\n\n")
        f.write("Daily Statistics 📊 :\n\n")
        cursor.execute("SELECT type, COUNT(*), SUM(duration) FROM distractions WHERE start_time LIKE ? GROUP BY type", (f'{now[:10]}%',))
        stats = cursor.fetchall()
        for stat in stats:
            type_, count, total_duration = stat
            f.write(f"{type_}: Number of cases:{count} ،Total time: {total_duration:.2f} second\n")

        f.write("\n📋 Details:\n\n")
        for r in records:
            f.write(f"ID: {r[0]} | Type: {r[1]} | From: {r[2]} | To: {r[3]} | Duration: {r[4]} second | location: {r[5]}\n")

    messagebox.showinfo("تم", f"تم توليد تقرير نصي:\n{file_path}")

def send_telegram_pdf(file_path):
    token = '7547616033:AAF6Mhdy0ma0rETUqP474LW03CsDvNTclfU'
    chat_id = '960702798'
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': chat_id}
            requests.post(url, files=files, data=data)
        messagebox.showinfo("تم", "تم إرسال التقرير إلى تيليجرام بنجاح")
    except Exception as e:
        messagebox.showerror("خطأ", f"فشل إرسال التقرير:\n{e}")

def generate_and_send_pdf_report(save_as=False, send_to_telegram=False):
    conn_thread = sqlite3.connect("distractions.db")
    cursor_thread = conn_thread.cursor()

    today = datetime.now().strftime('%Y-%m-%d')
    cursor_thread.execute("SELECT id, type, start_time, end_time, duration, location FROM distractions WHERE start_time LIKE ?", (f'{today}%',))
    records = cursor_thread.fetchall()
    if not records:
        messagebox.showinfo("لا يوجد", "لا توجد حالات اليوم.")
        conn_thread.close()
        return

    if save_as:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
            initialfile=f"daily_report_{today}.pdf"
        )
        if not file_path:
            conn_thread.close()
            return
    else:
        file_path = f"daily_report_{today}.pdf"

    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 50, f"Dispersion Report- {today}")

    y = height - 90
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Daily Statistics 📊 : ")
    y -= 20

    cursor_thread.execute("SELECT type, COUNT(*), SUM(duration) FROM distractions WHERE start_time LIKE ? GROUP BY type", (f'{today}%',))
    stats = cursor_thread.fetchall()
    c.setFont("Helvetica", 10)
    for stat in stats:
        type_, count, total_duration = stat
        c.drawString(50, y, f"{type_} :  Number of cases:{count} , Total time :{total_duration:.2f} ")
        y -= 15

    y -= 15
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, " Details 📋 :")
    y -= 20

    data = [["ID", "type", "start_time", "end_time", "duration (s)", "location"]] + list(records)
    table = Table(data, colWidths=[50, 80, 120, 120, 80, 150])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    table.wrapOn(c, width, height)
    table.drawOn(c, 30, y - (len(data) * 20))
    c.save()

    if send_to_telegram:
        send_telegram_pdf(file_path)

    conn_thread.close()
    if not send_to_telegram:
        messagebox.showinfo("تم", f"تم توليد تقرير PDF:\n{file_path}")

def schedule_daily_report():
    def check_time():
        while True:
            now = datetime.now()
            if now.hour == 0 and now.minute == 36:
                generate_and_send_pdf_report(send_to_telegram=True)
                time.sleep(60)
            time.sleep(30)

    threading.Thread(target=check_time, daemon=True).start()

# أزرار التحكم
button_frame = tk.Frame(root)
button_frame.pack(pady=10)

tk.Button(button_frame, text="🗑 حذف المحدد", command=delete_selected, bg="red", fg="black").pack(side="left", padx=5)
tk.Button(button_frame, text="🗑 حذف الكل", command=delete_all, bg="yellow", fg="black").pack(side="left", padx=5)
tk.Button(button_frame, text="📄 حفظ تقرير اليوم", command=lambda: generate_daily_report(True), bg="blue", fg="black").pack(side="left", padx=5)
tk.Button(button_frame, text="📄 حفظ تقرير PDF", command=lambda: generate_and_send_pdf_report(True), bg="green", fg="black").pack(side="left", padx=5)
tk.Button(button_frame, text="📤 إرسال تقرير PDF للتلجرام", command=lambda: generate_and_send_pdf_report(False, True), bg="orange", fg="black").pack(side="left", padx=5)

load_data()
schedule_daily_report()
root.mainloop()
conn.close()

