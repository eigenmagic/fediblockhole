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
checksum/config-secrets: {{ include ( print $.Template.BasePath "/secrets.yaml" ) . | sha256sum | quote }}
checksum/config-configmap: {{ include ( print $.Template.BasePath "/configmap-env.yaml" ) . | sha256sum | quote }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "fediblockhole.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "fediblockhole.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Get the fediblockhole secret.
*/}}
{{- define "fediblockhole.secretName" -}}
{{- if .Values.fediblockhole.secrets.existingSecret }}
    {{- printf "%s" (tpl .Values.fediblockhole.secrets.existingSecret $) -}}
{{- else -}}
    {{- printf "%s" (include "common.names.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/*
Return true if a fediblockhole secret object should be created
*/}}
{{- define "fediblockhole.createSecret" -}}
{{- if (not .Values.fediblockhole.secrets.existingSecret) -}}
    {{- true -}}
{{- end -}}
{{- end -}}
