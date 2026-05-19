import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    database="Desenrola",
    user="root",
    password="root"
)

cursor = conn.cursor()
cursor.execute("SELECT * FROM usuarios")
rows = cursor.fetchall()

conn.close()

from flask import Flask, render_template


app = Flask(__name__)

@app.route('/')
def principal():
    return render_template('Alunos.html')

if __name__ == '__main__':
    app.run(debug=True) 
