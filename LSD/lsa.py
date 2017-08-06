#!/usr/bin/env python3

import sys
import os
from datetime import datetime
import time
import argparse
import plotly
from plotly.graph_objs import *
import plotly.figure_factory as ff
from plotly import tools
import rethinkdb as r

# Preview: https://www.w3schools.com/html/tryit.asp?filename=tryhtml_basic
# Color: http://hex-color.com/web-safe-hex-colors

# Queries TODO
# License usage
# security per repository/category -> balkendiagram
# List packages with sig available
# List packages with https available


class LSA(object):
    def __init__(self, output='.', force=False, archlinux=None, gpg=None):
        self.output=output
        self.force = force
        self.archlinux = archlinux
        self.gpg = gpg
        self.time = time.strftime("%d/%m/%Y %H:%M:%S")

        # TODO import from local submodule?:
        # https://github.com/plotly/plotly.js/tree/fab0ba47b1db1a109476f17ad6b7f7e824eac0c1/dist
        # also in ./usr/lib/python3.6/site-packages/plotly/package_data/plotly.min.js
        self.div = '<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>\n'

    def error(self, *args):
        print('Error:', *args)
        sys.exit(1)

    def warning(self, *args):
        print('Warning:', *args)

    def plot_gpg(self):
        colors = ['#2CA02C', '#0077BB', '#FF7F0E', '#D62728', '#9467BD']
        trace = Pie(labels=self.gpg['algorithms'], values=self.gpg['counts'], marker=dict(colors=colors), sort=False)
        self.plot('GPG Key Distribution', [trace], timestamp=True, extra_text='<b>Other Algorithms:</b><br>' + '<br>'.join(self.gpg['other_algos']))

    def plot_archlinux(self, data, name):
        # Prepare graph data
        queries = [
            data['security'],
            data['sec_gpg'],
            data['sec_sig'],
            data['sec_https'],
            data['sec_hash']
        ]
        labels = ['EXCELLENT', 'HIGH', 'MID', 'LOW', 'NA']
        colors = ['#0077BB', '#2CA02C', '#FF7F0E', '#D62728', '#9467BD']
        titles = ['Package', 'GPG Key', 'Signature', 'HTTPS', 'Hash']

        # Generate pie diagrams
        for i, query in enumerate(queries):
            traces = []
            buttons = []

            # Create initial x and y tabel axis
            data_matrix = [ ['Security'], ['Total']]
            for l in labels:
                data_matrix += [[l]]

            if titles[i] == 'Signature' or titles[i] == 'HTTPS':
                data_matrix += [['Unused {}'.format(titles[i])]]

            for j, repo in enumerate(query):
                data_matrix[0] += [repo]
                values = []

                # Calculate total
                total = 0
                for label in labels:
                    if label in query[repo]:
                        total += query[repo][label]
                data_matrix[1] += ['{:>5} ({:.1f}%)'.format(total, 100)]

                # Add data to table and pie chart
                for k, label in enumerate(labels):
                    val = 0
                    if label in query[repo]:
                        val = query[repo][label]
                    values += [val]
                    data_matrix[2+k] += ['{:>5} ({: 5.1f}%)'.format(val, val*100/total)]

                # Add extra line for possible available Signature and HTTPS
                if titles[i] == 'Signature':
                    val = 0
                    if repo in data['avail_sigs']:
                        val = data['avail_sigs'][repo]
                    # TODO add links to lists of available signatures/https
                    data_matrix[2 + len(labels)] += ['{:>5} ({: 5.1f}%)'.format(val, val*100/total)]
                if titles[i] == 'HTTPS':
                    val = 0
                    if repo in data['avail_https']:
                        val = data['avail_https'][repo]
                    data_matrix[2 + len(labels)] += ['{:>5} ({: 5.1f}%)'.format(val, val*100/total)]

                trace = Pie(labels=labels, values=values, marker=dict(colors=colors), visible=False, name=repo, sort=False)
                #trace['domain']= {'x': [0, 1], 'y': [.5, 1]} # TODO reanable https://github.com/plotly/plotly.py/issues/790
                traces += [trace]

                # Generate updatemenu button
                visible = [False] * (len(query) + 1)
                visible[j] = True
                #visible[j + 1] = True # TODO renable https://github.com/plotly/plotly.py/issues/790
                #visible[0] = True
                buttons += [dict(label = repo, method = 'update',
                                 args = [{'visible': visible},
                                         {'title': repo + ' ' + titles[i] + ' Security'}])]
                # buttons += [dict(label = repo, method = 'restyle',
                #                  args = ['visible', visible])]
            # Add menu to select between Total and repositories
            updatemenus = list([
                dict(type="buttons",
                     showactive = True,
                     buttons=buttons
                )
            ])

            # Default: Total
            traces[0]['visible'] = True
            title = buttons[0]['args'][1]['title']
            self.plot(title, traces, updatemenus=updatemenus, timestamp=True)

            # Add table and trace data to figure
            figure = ff.create_table(data_matrix, index=True)

            # Use monospace font for data values
            columns = int(len(figure.layout.annotations) / len(data_matrix))
            for row in range(1, len(data_matrix)):
                for column in range(1, columns):
                    index = row * columns + column
                    figure.layout.annotations[index].font.family='Courier New, monospace'

            figure.layout.update({'title': title + ' Table'})
            self.plot_figure(figure)

            # # TODO renable https://github.com/plotly/plotly.py/issues/790
            # figure['data'].extend(Data(traces))
            #
            # # Edit layout for subplots
            # figure.layout.yaxis.update({'domain': [0, .4]})
            #
            # # The graph's yaxis2 MUST BE anchored to the graph's xaxis2 and vice versa
            # # Update the margins to add a title and see graph x-labels.
            # figure.layout.margin.update({'t': 75, 'l': 0}) # TODO 0 or 50? default 50, but with table not useful?
            # figure.layout.update({'title': titles[i] + ' Security'})
            # # Update the height because adding a graph vertically will interact with
            # # the plot height calculated for the table
            # figure.layout.update({'height': 600})
            # figure.layout.update({'width': 1000}) # TODO fix table length and remove
            # figure.layout.update({'updatemenus': updatemenus})
            #
            # #self.plot_figure(figure) # TODO renable https://github.com/plotly/plotly.py/issues/790


        # # Generate 4 pie diagrams
        # domains = [
        #     {'x': [0, .48], 'y': [0, .49]},
        #     {'x': [.52, 1], 'y': [0, .49]},
        #     {'x': [0, .48], 'y': [.51, 1]},
        #     {'x': [.52, 1], 'y': [.51, 1]}
        # ]
        # pie_traces = []
        # for i, query in enumerate(queries[1:], start=1):
        #     values = []
        #     for label in labels:
        #         if label in query['Total']:
        #             values += [query['Total'][label]]
        #         else:
        #             values += [0]
        #     trace = Pie(labels=labels, values=values, marker=dict(colors=colors), domain=domains[i-1])
        #     pie_traces += [trace]
        # self.plot('Security Distribution2', pie_traces)

        # Generate stacked bar diagram
        bar_traces = []
        for i, label in enumerate(labels):
            values = []
            for query in queries:
                if label in query['Total']:
                    values += [query['Total'][label]]
                else:
                    values += [0]
            trace = Bar(x=titles, y=values, name=label, marker=dict(color=colors[i]))
            bar_traces += [trace]
        self.plot('Security Distribution', bar_traces, barmode='stack')


        # values = [data['count']['Total'] - data['avail_sigs']['Total']]
        # for repo in data['repositories']:
        #     val = 0
        #     if repo in data['avail_sigs']:
        #         val = data['avail_sigs'][repo]
        #     values += [val]
        #
        # trace = Pie(labels=['Rest'] + data['repositories'], values=values)
        # self.plot('sigs', [trace])


        # Generate table for available signatures and https
        data_matrix = [['Repository', 'Available Signatures', 'Available HTTPS', 'Total Packages']]
        columns = ['avail_sigs', 'avail_https', 'count']

        # Generate each table row
        traces = []
        for repo in ['Total'] + data['repositories']:
            # Generate table
            dataset = []
            for colum in columns:
                if repo in data[colum]:
                    dataset += [data[colum][repo]]
                else:
                    dataset += [0]
            data_matrix += [[repo] + dataset]

            # Generate bar chart data
            trace = Bar(
                x=data_matrix[0][1:],
                y=dataset,
                xaxis='x2', yaxis='y2',
                name=repo
            )
            traces += [trace]

        # Add table and trace data to figure
        figure = ff.create_table(data_matrix)
        figure['data'].extend(Data(traces))

        # Edit layout for subplots
        figure.layout.yaxis.update({'domain': [0, .45]})
        figure.layout.yaxis2.update({'domain': [.6, 1]})
        # The graph's yaxis2 MUST BE anchored to the graph's xaxis2 and vice versa
        figure.layout.yaxis2.update({'anchor': 'x2'})
        figure.layout.xaxis2.update({'anchor': 'y2'})
        figure.layout.yaxis2.update({'title': 'Packages'})
        # Update the margins to add a title and see graph x-labels.
        figure.layout.margin.update({'t':75, 'l':50})
        figure.layout.update({'title': 'Unused GPG Signatures and HTTPS'})
        # Update the height because adding a graph vertically will interact with
        # the plot height calculated for the table
        figure.layout.update({'height':600})
        self.plot_figure(figure)

        for repo, pkglist in data['avail_sigs_list'].items():
            outfile = os.path.join(self.output, repo + '_sig.txt')
            with open(outfile, "w") as text_file:
                for pkg in pkglist:
                    print(pkg['name'] + ': ' + ', '.join(pkg['avail_sigs']), file=text_file)
            print('Output written to', outfile)

        for repo, pkglist in data['avail_https_list'].items():
            outfile = os.path.join(self.output, repo + '_https.txt')
            with open(outfile, "w") as text_file:
                for pkg in pkglist:
                    print(pkg['name'] + ': ' + ', '.join(pkg['avail_https']), file=text_file)
            print('Output written to', outfile)

    def plot(self, title, trace, barmode=None, updatemenus=None, timestamp=False, extra_text=None):
        if updatemenus:
            layout = Layout(title=title, barmode=barmode, updatemenus=updatemenus)
        else:
            layout = Layout(title=title, barmode=barmode)
        fig = Figure(data=trace, layout=layout)
        self.plot_figure(fig, timestamp=timestamp, extra_text=extra_text)

    def plot_figure(self, figure, timestamp=False, extra_text=None):
        annotations = []
        if timestamp:
            annotations += [
                dict(
                    text=self.time,
                    x=1,
                    y=0,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                )
            ]
        if extra_text:
            annotations += [
                dict(
                    text=extra_text,
                    x=0,
                    y=0,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    xanchor='left',
                    align='left',
                )
            ]
        if annotations:
            figure.layout.update({'annotations': annotations})

        filename = figure.layout.title.lower().replace(' ', '_') + '.div'
        div = plotly.offline.plot(figure, include_plotlyjs=False, output_type='div', show_link=False)
        self.div += div + '\n'

        path = os.path.join(self.output, filename)
        with open(path, "w") as text_file:
            print(div, file=text_file)
            #print(div)
        print('Output written to', path)

        # TODO export to png
        #plotly.offline.plot(figure, include_plotlyjs=False, output_type='png', show_link=False)
        #plotly.offline.plot(figure, auto_open=True, image='png', image_filename=os.path.join(self.output, figure.layout.title + '.png'))
        #sys.exit()
        #filename=os.path.join(self.output, figure.layout.title + '.png'))

    def print_div(self):
        # TODO add a pure image variant and this interactive version
        html = '<!DOCTYPE html><html><body>' + self.div + '</body></html>'
        path = os.path.join(self.output, 'index.html')
        with open(path, "w") as text_file:
            print(html, file=text_file)
            #print(html)
        print('Output written to', path)

    def evaluate(self):
        if self.archlinux:
            self.plot_archlinux(self.archlinux, 'ArchLinux')
        if self.gpg:
            self.plot_gpg()
        self.print_div()
