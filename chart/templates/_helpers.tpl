{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "fediblockhole.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "fediblockhole.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "fediblockhole.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "fediblockhole.labels" -}}
helm.sh/chart: {{ include "fediblockhole.chart" . }}
{{ include "fediblockhole.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "fediblockhole.selectorLabels" -}}
app.kubernetes.io/name: {{ include "fediblockhole.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Rolling pod annotations
*/}}
{{- define "fediblockhole.rollingPodAnnotations" -}}
rollme: {{ .Release.Revision | quote }}
checksum/config-configmap: {{ include ( print $.Template.BasePath "/configmap-conf-toml.yaml" ) . | sha256sum | quote }}
{{- end }}

{{/*
Create the default conf file path and filename
*/}}
{{- define "fediblockhole.conf_file_path" -}}
{{- default "/etc/default/" .Values.fediblockhole.conf_file.path }}
{{- end }}
{{- define "fediblockhole.conf_file_filename" -}}
{{- default "fediblockhole.conf.toml" .Values.fediblockhole.conf_file.filename }}
{{- end }}
