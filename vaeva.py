from wallbox import Wallbox, Statuses
import datetime
from yaml import load, dump
from yaml import Loader, Dumper
from jinja2 import Environment, FileSystemLoader, select_autoescape
from collections import namedtuple
from pprint import pprint
import argparse
import dateparser
from weasyprint import HTML, CSS

users = {}
sites = {}
outputs = {}
sessions = []
email_to_user = {}
badge_to_user = {}
args = None

User = namedtuple('User', ['id', 'name', 'email', 'badge', 'street', 'postcode', 'city'])
Site = namedtuple('Site', ['id', 'name', 'type', 'login', 'password'])
Output = namedtuple('Output', ['id', 'name', 'data', 'template', 'filename', 'renderer'])
Session = namedtuple('Session', ['site', 'charger', 'user', 'email', 'badge', 'date', 'duration', 'quantity', 'amount'])


def bom():
    d = datetime.datetime.today()
    return datetime.datetime(d.year, d.month, 1)


def eolm():
    return bom() - datetime.timedelta(1)


def bolm():
    d = eolm()
    return datetime.datetime(d.year, d.month, 1)


def load_config():
    global users, email_to_user, badge_to_user, sites, outputs, args

    parser = argparse.ArgumentParser(
                    prog='vaeva',
                    description='Vendor agnostic EV analytics',
                    epilog='Vaeva allows you to download data from car chargers and generate reports using jinja2 templates. Currently Wallbox and Easee car chargers are supported.')

    parser.add_argument('begin', help='Begin date (bom, bolm or dateparser format)')
    parser.add_argument('end', help='End date (eolm or dateparser format)')
    parser.add_argument('-s', '--site', dest='site', help='Site to process, default is all sites')
    parser.add_argument('-u', '--user', dest='user', help='User to process, default is all users')
    parser.add_argument('-o', '--output', dest='output', help='Outputs to generate, default is all outputs')
    parser.add_argument('-c', '--config', dest='config', default='vaeva.yml', help='Full path of the config file, default is vaeva.yml')
    args = parser.parse_args()

    if args.begin == 'bom':
        args.begin_date = bom()
    elif args.begin == 'bolm':
        args.begin_date = bolm()
    else:
        args.begin_date = dateparser.parse(args.begin)
    args.begin_date = args.begin_date.replace(hour=0, minute=0, second=0, microsecond=0)

    if args.end == 'eolm':
        args.end_date = eolm()
    else:
        args.end_date = dateparser.parse(args.end)
    args.end_date = args.end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    with open(args.config) as config_file:
        config = load(config_file, Loader=Loader)

        # load users
        for id, u in config['users'].items():
            email = u.get('email')
            badge = u.get('badge')
            users[id] = User(id=id, name=u.get('name',''), email=email, badge=badge, street=u.get('street',''), postcode=u.get('postcode',''), city=u.get('city',''))
            if email is not None:
                email_to_user[email] = id
            if badge is not None:
                badge_to_user[badge] = id

        # load sites
        for id, s in config['sites'].items():
            sites[id] = Site(id=id, name=s.get('name'), type=s.get('type'), login=s.get('login'), password=s.get('password'))

        # load outputs
        for id, o in config['output'].items():
            outputs[id] = Output(id=id, name=o.get('name'), filename=o.get('filename'), template=o.get('template'), data=o.get('data'), renderer=o.get('renderer','file'))


def add_session(site, charger, email='', badge='', date=None, duration=0, quantity=0, amount=0.0):
    global sessions, email_to_user, badge_to_user
    user = email_to_user.get(email, badge_to_user.get(badge))
    if user is not None:
        sessions.append(Session(site, charger, user, email, badge, date, duration, round(quantity,3), round(amount,2)))


def process_wallbox(site):
    w = Wallbox(site.login, site.password)
    w.authenticate()
    
    chargers = w.getChargersList()
    for charger in chargers:
        sessions = w.getSessionList(charger, args.begin_date, args.end_date)
        for session in sessions['data']:
            session_data = session['attributes']
            add_session(site.id, charger, session_data['user_email'], session_data['user_rfid'], datetime.datetime.fromtimestamp(session_data['start']), session_data['time'], session_data['energy'], session_data['cost'])


def process_easee(site):
    pass


def process_site(site):
    print('Loading data from site', site.name, '({})'.format(site.id))
    if site.type == 'wallbox':
        process_wallbox(site)
    elif site.type == 'easee':
        process_easee(site)
    else:
        raise ValueError('Unknown site type {}'.format(site.type))


def calculate_totals(data):
    total_quantity = 0.0
    total_amount = 0.0
    for session in data['sessions']:
        total_quantity += session.quantity
        total_amount += session.amount
    data['total'] = {'quantity' : round(total_quantity,3), 'amount' : round(total_amount,2)}


def generate_output(output):
    variables = {}
    data = {}
    data['meta'] = {'begin_date' : args.begin_date, 'end_date' : args.end_date, 'today' : datetime.datetime.today()}

    # generate one history report
    if output.data =='history':
        data['sessions'] =  sessions
        calculate_totals(data)
        render_template(output, data, variables)

    # generate one report per user
    if output.data == 'user':
        for user in users.values():
            variables = user._asdict()
            data['sessions'] = [session for session in sessions if session.email == user.email or session.badge == user.badge]
            data['user'] = user._asdict()
            calculate_totals(data)
            render_template(output, data, variables)


def render_template(output, data, variables):
    filename = output.filename
    for k, v in variables.items():
        filename = filename.replace('{{'+k+'}}', v)
    print('Generating output', output.name, '({})'.format(filename))
    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape()
    )
    template = env.get_template(output.template)
    content = template.render(data)

    if output.renderer == 'file':
        with open(filename, 'w') as f:
            f.write(content)
    elif output.renderer == 'pdf':
        html = HTML(string=content)
        css = CSS(filename='vaeva.css')
        html.write_pdf(filename, stylesheets=[css])


def sort_session(s):
    return s.date


def main():
    load_config()

    print('Using range from', args.begin_date, 'to', args.end_date)

    # if no site is specified, process all sites, otherwise only the requested site
    if args.site is None:
        for site in sites.values():
            process_site(site)
    else:
        process_site(sites[args.site])

    sessions.sort(key=sort_session)

    # generate outputs
    if args.output is None:
        for output in outputs.values():
            generate_output(output)
    else:
        generate_output(outputs[args.output])


if __name__ == "__main__":
    main()