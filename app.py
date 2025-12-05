"""
Know Your Constituency - Delhi NCR
Flask Web Application (file-based, no pandas)
Enhanced to handle multiple VS per pincode and LS-name normalization
"""

from flask import Flask, render_template, request
import csv, os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'school-project-2025'

DATA_DIR = 'data'

def load_csv_to_list(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def save_list_to_csv(filename, data, fieldnames):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(data)

def load_data():
    data = {}
    data['constituencies'] = load_csv_to_list('constituencies.csv')
    data['mps'] = load_csv_to_list('mps.csv')
    data['vs_constituencies'] = load_csv_to_list('vidhan_sabha_constituencies.csv')
    data['vs_mapping'] = load_csv_to_list('vidhan_sabha_constituency_mapping.csv')
    data['mlas'] = load_csv_to_list('delhi_mlas_2025.csv')
    # complaints
    if os.path.exists(os.path.join(DATA_DIR, 'complaints.csv')):
        data['complaints'] = load_csv_to_list('complaints.csv')
    else:
        data['complaints'] = []
        save_list_to_csv(
            'complaints.csv',
            data['complaints'],
            ['complaint_id','pincode','vs_id','complainant_name','complainant_email',
             'complainant_phone','complaint_description','complaint_category',
             'complaint_status','submitted_date']
        )
    return data

DATA = load_data()

# Helpers
def normalize_ls_name(name):
    if not name:
        return None
    name = name.strip()
    replacements = {
        'North East Delhi': 'North-East Delhi',
        'North West Delhi': 'North-West Delhi',
        'South East Delhi': 'East Delhi',
    }
    return replacements.get(name, name)

def find_ls_by_name(name):
    if not name:
        return None
    norm = normalize_ls_name(name)
    for ls in DATA['constituencies']:
        if ls['constituency_name'] == norm:
            return ls
    return None

def find_mp_by_ls(ls_row):
    if not ls_row:
        return None
    ls_id = ls_row['constituency_id']
    for mp in DATA['mps']:
        if mp['constituency_id'] == ls_id:
            return mp
    return None

def find_vs_by_id(vs_id):
    for vs in DATA['vs_constituencies']:
        if vs['vs_id'] == str(vs_id):
            return vs
    return None

def find_mla_by_vs_id(vs_id):
    for mla in DATA['mlas']:
        if mla['vs_id'] == str(vs_id):
            return mla
    return None

def vs_options_for_pincode(pincode):
    # Return all rows for this pincode as options, de-duplicated by vs_id
    opts = [row for row in DATA['vs_mapping'] if row['pincode'] == str(pincode)]
    # Some mappings may repeat same vs_id for multiple localities; keep first
    seen, uniq = set(), []
    for r in opts:
        key = r['vs_id']
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    return uniq

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET','POST'])
def search():
    if request.method == 'POST':
        pincode = request.form.get('pincode','').strip()
        chosen_vs_id = request.form.get('vs_id','').strip()

        if not (pincode.isdigit() and len(pincode)==6):
            return render_template('search.html', error="Please enter a valid 6-digit pincode")

        options = vs_options_for_pincode(pincode)

        if not options:
            return render_template('search.html', error=f"No constituency found for pincode {pincode}", pincode=pincode)

        # If multiple and no vs selected yet, render chooser
        if len(options) > 1 and not chosen_vs_id:
            # Provide options for user to select a specific Assembly seat
            return render_template('search.html',
                                   pincode=pincode,
                                   vs_options=options,
                                   choose_vs=True)

        # Determine the target VS row: either selected, or the only option
        target = None
        if chosen_vs_id:
            for r in options:
                if r['vs_id'] == chosen_vs_id:
                    target = r
                    break
        else:
            target = options[0]

        vs_details = find_vs_by_id(target['vs_id'])
        mla = find_mla_by_vs_id(target['vs_id'])

        # Lok Sabha
        ls_from_mapping = target.get('lok_sabha_constituency')
        ls_row = find_ls_by_name(ls_from_mapping if ls_from_mapping else (vs_details.get('lok_sabha_constituency') if vs_details else None))
        mp = find_mp_by_ls(ls_row)

        return render_template('search.html',
                               pincode=pincode,
                               locality=target.get('locality',''),
                               vs_name=target.get('vs_name',''),
                               vs_details=vs_details,
                               mla=mla,
                               ls_name=ls_row['constituency_name'] if ls_row else None,
                               ls_details=ls_row,
                               mp=mp)

    # GET
    return render_template('search.html')

@app.route('/complaint', methods=['GET','POST'])
def complaint():
    if request.method == 'POST':
        pincode = request.form.get('pincode','').strip()
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip()
        phone = request.form.get('phone','').strip()
        category = request.form.get('category','').strip()
        description = request.form.get('description','').strip()
        chosen_vs_id = request.form.get('vs_id','').strip()

        if not (pincode.isdigit() and len(pincode)==6):
            return render_template('complaint.html', error="Please enter a valid 6-digit pincode")
        if not name:
            return render_template('complaint.html', error="Please enter your name", pincode=pincode)
        if '@' not in email:
            return render_template('complaint.html', error="Please enter a valid email", pincode=pincode)
        if not description:
            return render_template('complaint.html', error="Please enter complaint description", pincode=pincode)

        options = vs_options_for_pincode(pincode)
        if not options:
            return render_template('complaint.html', error="Pincode not found in Delhi NCR", pincode=pincode)

        # If multiple and no vs chosen, present chooser on the same page
        if len(options) > 1 and not chosen_vs_id:
            return render_template('complaint.html',
                                   pincode=pincode,
                                   name=name, email=email, phone=phone,
                                   category=category, description=description,
                                   vs_options=options, choose_vs=True)

        # Resolve vs_id
        vs_id = chosen_vs_id if chosen_vs_id else options[0]['vs_id']

        complaint_id = len(DATA['complaints']) + 1
        DATA['complaints'].append({
            'complaint_id': str(complaint_id),
            'pincode': pincode,
            'vs_id': vs_id,
            'complainant_name': name,
            'complainant_email': email,
            'complainant_phone': phone,
            'complaint_description': description,
            'complaint_category': category,
            'complaint_status': 'NEW',
            'submitted_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        save_list_to_csv('complaints.csv', DATA['complaints'],
                         ['complaint_id','pincode','vs_id','complainant_name','complainant_email',
                          'complainant_phone','complaint_description','complaint_category',
                          'complaint_status','submitted_date'])
        return render_template('complaint.html', success=True, complaint_id=complaint_id)

    return render_template('complaint.html')

@app.route('/status', methods=['GET','POST'])
def status():
    if request.method == 'POST':
        cid = request.form.get('complaint_id','').strip()
        if not (cid.isdigit()):
            return render_template('status.html', error="Please enter a valid complaint ID")
        for c in DATA['complaints']:
            if c['complaint_id'] == cid:
                return render_template('status.html', complaint=c)
        return render_template('status.html', error="No complaint found with this ID")
    return render_template('status.html')

@app.route('/stats')
def stats():
    try:
        DATA['complaints'] = load_csv_to_list('complaints.csv')
    except:
        pass
    total = len(DATA['complaints'])
    resolved = sum(1 for c in DATA['complaints'] if c.get('complaint_status')=='RESOLVED')
    new = sum(1 for c in DATA['complaints'] if c.get('complaint_status')=='NEW')
    prog = sum(1 for c in DATA['complaints'] if c.get('complaint_status')=='IN_PROGRESS')
    stats = {
        'total_lok_sabha': len(DATA['constituencies']),
        'total_vidhan_sabha': len(DATA['vs_constituencies']),
        'total_pincodes': len(DATA['vs_mapping']),
        'total_complaints': total,
        'resolved_complaints': resolved,
        'new_complaints': new,
        'in_progress': prog,
        'resolution_rate': (resolved/total*100) if total>0 else 0
    }
    # category counts
    cats = {}
    for c in DATA['complaints']:
        k = c.get('complaint_category','Other')
        cats[k] = cats.get(k,0)+1
    return render_template('stats.html', stats=stats, categories=cats)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8080)
